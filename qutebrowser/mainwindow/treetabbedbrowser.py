# SPDX-FileCopyrightText: Giuseppe Stelluto (pinusc) <giuseppe@gstelluto.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Subclass of TabbedBrowser to provide tree-tab functionality."""

import collections
import dataclasses
import datetime
from typing import List, Dict
from qutebrowser.qt.widgets import QSizePolicy
from qutebrowser.qt.core import pyqtSlot, QUrl

from qutebrowser.config import config
from qutebrowser.mainwindow.tabbedbrowser import TabbedBrowser
from qutebrowser.mainwindow.treetabwidget import TreeTabWidget
from qutebrowser.browser import browsertab
from qutebrowser.misc import notree
from qutebrowser.utils import log


@dataclasses.dataclass
class _TreeUndoEntry():
    """Information needed for :undo."""

    url: QUrl
    history: bytes
    index: int
    pinned: bool
    uid: int
    parent_node_uid: int
    children_node_uids: List[int]
    local_index: int  # index of the tab relative to its siblings
    created_at: datetime.datetime = dataclasses.field(
        default_factory=datetime.datetime.now)

    @staticmethod
    def from_node(node, idx):
        """Make a TreeUndoEntry from a Node."""
        url = node.value.url()
        try:
            history_data = node.value.history.private_api.serialize()
        except browsertab.WebTabError:
            history_data = []
        pinned = node.value.data.pinned
        uid = node.uid
        parent_uid = node.parent.uid
        children = [n.uid for n in node.children]
        local_idx = node.index
        return _TreeUndoEntry(url=url,
                              history=history_data,
                              index=idx,
                              pinned=pinned,
                              uid=uid,
                              parent_node_uid=parent_uid,
                              children_node_uids=children,
                              local_index=local_idx)


class TreeTabbedBrowser(TabbedBrowser):
    """Subclass of TabbedBrowser to provide tree-tab functionality.

    Extends TabbedBrowser methods (mostly tabopen, undo, and _remove_tab) so
    that the internal tree is updated after every action.

    Provides methods to hide and show subtrees, and to cycle visibility.
    """

    is_treetabbedbrowser = True

    def __init__(self, *, win_id, private, parent=None):
        super().__init__(win_id=win_id, private=private, parent=parent)
        self.is_treetabbedbrowser = True
        self.widget = TreeTabWidget(win_id, parent=self)
        self.widget.tabCloseRequested.connect(self.on_tab_close_requested)
        self.widget.new_tab_requested.connect(self.tabopen)
        self.widget.currentChanged.connect(self._on_current_changed)
        self.cur_fullscreen_requested.connect(self.widget.tabBar().maybe_hide)
        self.widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._reset_stack_counters()

    def _remove_tab(self, tab, *, add_undo=True, new_undo=True, crashed=False):
        """Handle children positioning after a tab is removed."""
        node = tab.node
        # FIXME after the fixme in _add_undo_entry is resolved, no need
        # to save descendents
        descendents = tuple(node.traverse(render_collapsed=True))

        if not tab.url().isEmpty() and tab.url().isValid() and add_undo:
            idx = self.widget.indexOf(tab)
            self._add_undo_entry(tab, idx, new_undo)

        parent = node.parent

        if node.collapsed:
            # Collapsed nodes have already been removed from the TabWidget so
            # we can't ask super() to dispose of them and need to do it
            # ourselves.
            for descendent in descendents:
                descendent.parent = None
                descendent_tab = descendent.value
                descendent_tab.private_api.shutdown()
                descendent_tab.deleteLater()
                descendent_tab.layout().unwrap()
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

    def _add_undo_entry(self, tab, idx, new_undo):
        """Save undo entry with tree information.

        This function was removed in tabbedbrowser, but it is still useful here because
        the mechanism is quite a bit more complex
        """
        # TODO see if it's possible to remove duplicate code from
        # super()._add_undo_entry
        node = tab.node
        if not node.collapsed:
            entry = _TreeUndoEntry.from_node(node, 0)
            if new_undo or not self.undo_stack:
                self.undo_stack.append([entry])
            else:
                self.undo_stack[-1].append(entry)
        else:
            entries = []
            for descendent in node.traverse(notree.TraverseOrder.POST_R):
                entry = _TreeUndoEntry.from_node(descendent, 0)
                # Recursively removed nodes will never have any children
                # in the tree they are being added into. Children will
                # always be added later as the undo stack is worked
                # through.
                # UndoEntry.from_node() is not clever enough enough to
                # handle this case on its own currently.
                entry.children_node_uids = []
                entries.append(entry)
            if new_undo:
                self.undo_stack.append(entries)
            else:
                self.undo_stack[-1] += entries

    def undo(self, depth=1):
        """Undo removing of a tab or tabs."""
        # TODO find a way to remove dupe code
        # probably by getting entries from undo stack, THEN calling super
        # then post-processing the entries

        # save entries before super().undo() pops them
        entries = list(self.undo_stack[-depth])
        new_tabs = super().undo(depth)

        for entry, tab in zip(reversed(entries), new_tabs):
            if not isinstance(entry, _TreeUndoEntry):
                continue
            root = self.widget.tree_root
            uid = entry.uid
            parent_uid = entry.parent_node_uid
            parent_node = root.get_descendent_by_uid(parent_uid)
            if not parent_node:
                parent_node = root

            children = []
            for child_uid in entry.children_node_uids:
                child_node = root.get_descendent_by_uid(child_uid)
                children.append(child_node)
            tab.node.parent = None  # Remove the node from the tree
            tab.node = notree.Node(tab, parent_node,
                                   children, uid)

            # correctly reposition the tab
            local_idx = entry.local_index
            if tab.node.parent:  # should always be true
                new_siblings = list(tab.node.parent.children)
                new_siblings.remove(tab.node)
                new_siblings.insert(local_idx, tab.node)
                tab.node.parent.children = new_siblings

        self.widget.tree_tab_update()

    @pyqtSlot('QUrl')
    @pyqtSlot('QUrl', bool)
    @pyqtSlot('QUrl', bool, bool)
    def tabopen(
            self, url: QUrl = None,
            background: bool = None,
            related: bool = True,
            sibling: bool = False,
            idx: int = None,
    ) -> browsertab.AbstractTab:
        """Open a new tab with a given url.

        Args:
            related: Whether to set the tab as a child of the currently focused
                     tab. Follows `tabs.new_position.tree.related`.
            sibling: Whether to set the tab as a sibling of the currently
                     focused tab.  Follows `tabs.new_position.tree.sibling`.

        """
        # pylint: disable=arguments-differ
        # we save this now because super.tabopen also resets the focus
        cur_tab = self.widget.currentWidget()
        tab = super().tabopen(url, background, related, idx)

        tab.node.parent = self.widget.tree_root
        if cur_tab is None or tab is cur_tab:
            self.widget.tree_tab_update()
            return tab

        # get pos
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

        self._position_tab(cur_tab, tab, pos, parent, sibling, related, background)

        return tab

    def _position_tab(
        self,
        cur_tab: browsertab.AbstractTab,
        tab: browsertab.AbstractTab,
        pos: str,
        parent: notree.Node,
        sibling: bool = False,
        related: bool = True,
        background: bool = None,
    ) -> None:
        toplevel = not sibling and not related
        siblings = list(parent.children)
        if tab.node in siblings:  # true if parent is tree_root
            # remove it and add it later in the right position
            siblings.remove(tab.node)

        if pos == 'first':
            rel_idx = 0
            if config.val.tabs.new_position.stacking and related:
                rel_idx += self._tree_tab_child_rel_idx
                self._tree_tab_child_rel_idx += 1
            siblings.insert(rel_idx, tab.node)
        elif pos in ['prev', 'next'] and (sibling or toplevel):
            # pivot is the tab relative to which 'prev' or 'next' apply
            # it is always a member of 'siblings'
            pivot = cur_tab.node if sibling else cur_tab.node.path[1]
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
            siblings.insert(tgt_idx, tab.node)
        else:  # position == 'last'
            siblings.append(tab.node)
        parent.children = siblings
        self.widget.tree_tab_update()
        if not background:
            self._reset_stack_counters()

    def _reset_stack_counters(self):
        self._tree_tab_child_rel_idx = 0
        self._tree_tab_sibling_rel_idx = 0
        self._tree_tab_toplevel_rel_idx = 0

    @pyqtSlot(int)
    def _on_current_changed(self, idx):
        super()._on_current_changed(idx)
        self._reset_stack_counters()

    def cycle_hide_tab(self, node):
        """Utility function for tree_tab_cycle_hide command."""
        # height = node.height  # height is always rel_height
        if node.collapsed:
            node.collapsed = False
            for descendent in node.traverse(render_collapsed=True):
                descendent.collapsed = False
            return

        def rel_depth(n):
            return n.depth - node.depth

        levels: Dict[int, list] = collections.defaultdict(list)
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
