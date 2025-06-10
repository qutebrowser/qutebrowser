# SPDX-FileCopyrightText: Giuseppe Stelluto (pinusc) <giuseppe@gstelluto.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Subclass of TabbedBrowser to provide tree-tab functionality."""

import collections
import dataclasses
import functools
from typing import Optional, Union
from qutebrowser.qt.core import pyqtSlot, QUrl

from qutebrowser.config import config
from qutebrowser.mainwindow.tabbedbrowser import TabbedBrowser, _UndoEntry
from qutebrowser.mainwindow.treetabwidget import TreeTabWidget
from qutebrowser.browser import browsertab
from qutebrowser.misc import notree
from qutebrowser.qt.widgets import QTabBar


@dataclasses.dataclass
class _TreeUndoEntry(_UndoEntry):
    """Information needed for :undo."""

    uid: int
    parent_node_uid: int
    children_node_uids: list[int]
    local_index: int  # index of the tab relative to its siblings

    def restore_into_tab(self, tab: browsertab.AbstractTab) -> None:
        super().restore_into_tab(tab)

        root = tab.node.path[0]
        uid = self.uid
        parent_uid = self.parent_node_uid
        parent_node = root.get_descendent_by_uid(parent_uid)
        if not parent_node:
            parent_node = root

        children = []
        for child_uid in self.children_node_uids:
            child_node = root.get_descendent_by_uid(child_uid)
            if child_node:
                children.append(child_node)
        tab.node.parent = None  # Remove the node from the tree
        tab.node = notree.Node(tab, parent_node,
                               children, uid)

        # correctly reposition the tab
        local_idx = self.local_index
        if tab.node.parent:  # should always be true
            new_siblings = list(tab.node.parent.children)
            new_siblings.remove(tab.node)
            new_siblings.insert(local_idx, tab.node)
            tab.node.parent.children = new_siblings

    @classmethod
    def from_tab(
        cls,
        tab: browsertab.AbstractTab,
        idx: int,
        recursing: bool = False,
    ) -> Union["_TreeUndoEntry", list["_TreeUndoEntry"]]:
        """Make a TreeUndoEntry from a Node."""
        node = tab.node
        url = node.value.url()
        try:
            history_data = tab.history.private_api.serialize()
        except browsertab.WebTabError:
            return None  # special URL

        if not recursing and node.collapsed:
            entries = [
                cls.from_tab(descendent.value, idx+1, recursing=True)
                for descendent in
                node.traverse(notree.TraverseOrder.POST_R)
            ]
            entries = [entry for entry in entries if entry]
            return entries

        pinned = node.value.data.pinned
        uid = node.uid
        parent_uid = node.parent.uid
        if recursing:
            # Recursively removed nodes will never have any existing children
            # to re-parent in the tree they are being added into, children
            # will always be added later as the undo stack is worked through.
            # So remove child IDs here so we don't confuse undo() later.
            children = []
        else:
            children = [n.uid for n in node.children]
        local_idx = node.index
        return cls(
            url=url,
            history=history_data,
            # The index argument is redundant given the parent and local index
            # info, but required by the parent class.
            index=idx,
            pinned=pinned,
            uid=uid,
            parent_node_uid=parent_uid,
            children_node_uids=children,
            local_index=local_idx,
        )


class TreeTabbedBrowser(TabbedBrowser):
    """Subclass of TabbedBrowser to provide tree-tab functionality.

    Extends TabbedBrowser methods (mostly tabopen, undo, and _remove_tab) so
    that the internal tree is updated after every action.

    Provides methods to hide and show subtrees, and to cycle visibility.
    """

    is_treetabbedbrowser = True
    _undo_class = _TreeUndoEntry

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tree_tab_child_rel_idx = 0
        self._tree_tab_sibling_rel_idx = 0
        self._tree_tab_toplevel_rel_idx = 0

    def _create_tab_widget(self):
        """Return the tab widget that can display a tree structure."""
        return TreeTabWidget(self._win_id, parent=self)

    def _remove_tab(self, tab, *, add_undo=True, new_undo=True, crashed=False, recursive=False):
        """Handle children positioning after a tab is removed."""
        if not tab.url().isEmpty() and tab.url().isValid() and add_undo:
            self._add_undo_entry(tab, new_undo)

        if recursive:
            for descendent in tab.node.traverse(
                order=notree.TraverseOrder.POST_R,
                render_collapsed=False
            ):
                self.tab_close_prompt_if_pinned(
                    descendent.value,
                    False,
                    functools.partial(
                        self._remove_tab,
                        descendent.value,
                        add_undo=add_undo,
                        new_undo=new_undo,
                        crashed=crashed,
                        recursive=False,
                    )
                )
                new_undo = False
            return

        node = tab.node
        parent = node.parent
        current_tab = self.current_tab()

        # Override tabs.select_on_remove behavior to be tree aware.
        # The default behavior is in QTabBar.removeTab(), by way of
        # QTabWidget.removeTab(). But here we are detaching the tab from the
        # tree before those methods get called, so if we want to have a tree
        # aware behavior we need to implement that here by selecting the new
        # tab before the closing the current one.
        if tab == current_tab:
            selection_behavior = self.widget.tabBar().selectionBehaviorOnRemove()
            # Given a tree structure like:
            # - one
            #   - two
            # - three (active)
            # If the setting is "prev" (aka left) we want to end up with tab
            # "one" selected after closing tab "three". Switch to either the
            # current tab's previous sibling or its parent.
            if selection_behavior == QTabBar.SelectionBehavior.SelectLeftTab:
                siblings = parent.children
                rel_index = siblings.index(node)
                if rel_index == 0:
                    next_tab = parent.value
                else:
                    next_tab = siblings[rel_index-1].value
                self.widget.setCurrentWidget(next_tab)

        if node.collapsed:
            # Collapsed nodes have already been removed from the TabWidget so
            # we can't ask super() to dispose of them and need to do it
            # ourselves.
            for descendent in node.traverse(
                order=notree.TraverseOrder.POST_R,
                render_collapsed=True
            ):
                descendent.parent = None
                descendent_tab = descendent.value
                descendent_tab.private_api.shutdown()
                descendent_tab.deleteLater()
        elif parent:
            siblings = list(parent.children)
            children = node.children

            if children:
                # Promote first child,
                # make that promoted node the parent of our other children
                # give the promoted node our position in our siblings list.
                next_node = children[0]

                for n in children[1:]:
                    n.parent = next_node

                # swap nodes
                node_idx = siblings.index(node)
                siblings[node_idx] = next_node

                parent.children = tuple(siblings)
                assert not node.children

            node.parent = None

        super()._remove_tab(tab, add_undo=False, new_undo=False,
                            crashed=crashed)

        self.widget.tree_tab_update()

    def undo(self, depth: int = 1) -> None:
        """Undo removing of a tab or tabs."""
        super().undo(depth)
        self.widget.tree_tab_update()

    def tabs(
        self,
        include_hidden: bool = False,
    ) -> list[browsertab.AbstractTab]:
        """Get a list of tabs in this browser.

        Args:
            include_hidden: Include child tabs which are not currently in the
                            tab bar.
        """
        return [
            node.value
            for node
            in self.widget.tree_root.traverse(
                render_collapsed=include_hidden,
            )
            if node.value
        ]

    @pyqtSlot('QUrl')
    @pyqtSlot('QUrl', bool)
    @pyqtSlot('QUrl', bool, bool)
    def tabopen(
            self, url: QUrl = None,
            background: bool = None,
            related: bool = True,
            idx: int = None,
            sibling: bool = False,
    ) -> browsertab.AbstractTab:
        """Open a new tab with a given url.

        Args:
            related: Whether to set the tab as a child of the currently focused
                     tab. Follows `tabs.new_position.tree.related`.
            sibling: Whether to set the tab as a sibling of the currently
                     focused tab.  Follows `tabs.new_position.tree.sibling`.

        """
        # Save the current tab now before letting super create the new tab
        # (and possibly give it focus). To insert the new tab correctly in the
        # tree structure later we may need to know which tab it was opened
        # from (for the `related` and `sibling` cases).
        cur_tab = self.widget.currentWidget()
        tab = super().tabopen(url, background, related, idx)

        # Some trivial cases where we don't need to do positioning:

        # 1. this is the first tab in the window.
        if cur_tab is None:
            assert self.widget.count() == 1
            assert tab.node.parent == self.widget.tree_root
            return tab

        if (
            config.val.tabs.tabs_are_windows or  # 2. one tab per window
            tab is cur_tab                       # 3. opening URL in existing tab
        ):
            return tab

        # Some sanity checking to make sure the tab super created was set up
        # as a tree style tab correctly. We don't have a TreeTab so this is
        # heuristic to highlight any problems elsewhere in the application
        # logic.
        assert tab.node.parent, (
            f"Node for new tab doesn't have a parent: {tab.node}"
        )

        # We may also be able to skip the positioning code below if the `idx`
        # arg is passed in. Semgrep says that arg is used from undo() and
        # SessionManager, both cases are updating the tree structure
        # themselves after opening the new tab. On the other hand the only
        # downside is we move the tab and update the tree twice. Although that
        # may actually make loading large sessions a bit slower.

        if related:
            pos = config.val.tabs.new_position.tree.new_child
            parent = cur_tab.node
            # pos can only be first, last
        elif sibling:
            pos = config.val.tabs.new_position.tree.new_sibling
            parent = cur_tab.node.parent
            # pos can be first, last, prev, next
        else:
            pos = config.val.tabs.new_position.tree.new_toplevel
            parent = self.widget.tree_root

        self._position_tab(cur_tab.node, tab.node, pos, parent, sibling,
                           related, background, idx)

        return tab

    def _position_tab(  # pylint: disable=too-many-positional-arguments
        self,
        cur_node: notree.Node[object],
        new_node: notree.Node[object],
        pos: str,
        parent: notree.Node[object],
        sibling: bool = False,
        related: bool = True,
        background: Optional[bool] = None,
        idx: Optional[int] = None,
    ) -> None:
        toplevel = not sibling and not related
        siblings = list(parent.children)
        if new_node.parent == parent:
            # Remove the current node from its parent's children list to avoid
            # potentially adding it as a duplicate later.
            siblings.remove(new_node)

        if idx:
            sibling_indices = [self.widget.indexOf(node.value) for node in siblings]
            assert sibling_indices == sorted(sibling_indices)
            sibling_indices.append(idx)
            sibling_indices = sorted(sibling_indices)
            rel_idx = sibling_indices.index(idx)
            siblings.insert(rel_idx, new_node)
        elif pos == 'first':
            rel_idx = 0
            if config.val.tabs.new_position.stacking and related:
                rel_idx += self._tree_tab_child_rel_idx
                self._tree_tab_child_rel_idx += 1
            siblings.insert(rel_idx, new_node)
        elif pos in ['prev', 'next'] and (sibling or toplevel):
            # Pivot is the tab relative to which 'prev' or 'next' apply to.
            # Either the current node or top of the current tree.
            pivot = cur_node if sibling else cur_node.path[1]
            direction = -1 if pos == 'prev' else 1
            rel_idx = 0 if pos == 'prev' else 1
            tgt_idx = siblings.index(pivot) + rel_idx
            if config.val.tabs.new_position.stacking:
                if sibling:
                    tgt_idx += self._tree_tab_sibling_rel_idx
                    self._tree_tab_sibling_rel_idx += direction
                elif toplevel:
                    tgt_idx += self._tree_tab_toplevel_rel_idx
                    self._tree_tab_toplevel_rel_idx += direction
            siblings.insert(tgt_idx, new_node)
        else:  # position == 'last'
            siblings.append(new_node)

        parent.children = siblings
        self.widget.tree_tab_update()
        if not background:
            self._reset_stack_counters()

    def _reset_stack_counters(self) -> None:
        self._tree_tab_child_rel_idx = 0
        self._tree_tab_sibling_rel_idx = 0
        self._tree_tab_toplevel_rel_idx = 0

    @pyqtSlot(int)
    def _on_current_changed(self, idx: int) -> None:
        super()._on_current_changed(idx)
        self._reset_stack_counters()

    def cycle_hide_tab(self, node: notree.Node[object]) -> None:
        """Utility function for tree_tab_cycle_hide command."""
        # height = node.height  # height is always rel_height
        if node.collapsed:
            node.collapsed = False
            for descendent in node.traverse(render_collapsed=True):
                descendent.collapsed = False
            return

        def rel_depth(n: notree.Node[object]) -> int:
            return n.depth - node.depth

        levels: dict[int, list[notree.Node[object]]] = collections.defaultdict(list)
        for d in node.traverse(render_collapsed=False):
            r_depth = rel_depth(d)
            levels[r_depth].append(d)

        # Remove highest level because it's leaves (or already collapsed)
        del levels[max(levels.keys())]

        target = 0
        for level in sorted(levels, reverse=True):
            nodes = levels[level]
            if not all(n.collapsed or not n.children for n in nodes):
                target = level
                break
        for n in levels[target]:
            if not n.collapsed and n.children:
                n.collapsed = True
