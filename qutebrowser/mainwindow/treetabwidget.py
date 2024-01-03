# SPDX-FileCopyrightText: Giuseppe Stelluto (pinusc) <giuseppe@gstelluto.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Extension of TabWidget for tree-tab functionality."""

from qutebrowser.mainwindow.tabwidget import TabWidget
from qutebrowser.misc.notree import Node
from qutebrowser.utils import log


class TreeTabWidget(TabWidget):
    """Tab widget used in TabbedBrowser, with tree-functionality.

    Handles correct rendering of the tree as a tab field, and correct
    positioning of tabs according to tree structure.
    """

    def __init__(self, win_id, parent=None):
        # root of the tab tree, common for all tabs in the window
        self.tree_root = Node(None)
        super().__init__(win_id, parent)
        self.tabBar().tabMoved.disconnect(self.update_tab_titles)

    def _init_config(self):
        super()._init_config()
        # For tree-tabs
        self.update_tab_titles()  # Must also be called when deactivating
        self.tree_tab_update()

    def get_tab_fields(self, idx):
        """Add tree field data to normal tab field data."""
        fields = super().get_tab_fields(idx)

        if len(self.tree_root.children) == 0:
            # Presumably the window is still being initialized
            log.misc.vdebug(f"Tree root has no children. Are we starting up? fields={fields}")
            return fields

        rendered_tree = self.tree_root.render()
        tab = self.widget(idx)
        found = [
            prefix
            for prefix, node in rendered_tree
            if node.value == tab
        ]

        if len(found) == 1:
            # we remove the first two chars because every tab is child of tree
            # root and that gets rendered as well
            fields['tree'] = found[0][2:]
            fields['collapsed'] = '[...] ' if tab.node.collapsed else ''
            return fields

        # Beyond here we have a mismatch between the tab widget and the tree.
        # Try to identify known situations where this happens precisely and
        # handle them gracefully. Blow up on unknown situations so we don't
        # miss them.

        # Just sanity checking, we haven't seen this yet.
        assert len(found) == 0, (
            "Found multiple tree nodes with the same tab as value: tab={tab}"
        )

        # Having more tabs in the widget when loading a session with a
        # collapsed group in is a known case. Check for it with a heuristic
        # (for now) and assert if that doesn't look like that's how we got
        # here.
        all_nodes = self.tree_root.traverse()
        node = [n for n in all_nodes if n.value == tab][0]
        is_hidden = any(n.collapsed for n in node.path)

        tabs = [str(self.widget(idx)) for idx in range(self.count())]
        difference = len(rendered_tree) - 1 - len(tabs)
        # empty_urls here is a proxy for "there is a session being loaded into
        # this window"
        empty_urls = all(
            [self.widget(idx).url().toString() == "" for idx in range(self.count())]
        )
        if empty_urls and is_hidden:
            # All tabs will be added to the tab widget during session load
            # and they will only be removed later when the widget is
            # updated from the tree. Meanwhile, if we get here we'll have
            # hidden tabs present in the widget but absent from the node.
            # To detect this situation more clearly we could do something like
            # have a is_starting_up or is_loading_session attribute on the
            # tabwidget/tabbbedbrowser. Or have the session manager add all
            # nodes to the tree uncollapsed initially and then go through and
            # collapse them.
            log.misc.vdebug(
                "get_tab_fields() called with different amount of tabs in "
                f"widget vs in the tree: difference={difference} "
                f"tree={rendered_tree[1:]} tabs={tabs}"
            )
        else:
            # If we get here then we have another case to investigate.
            assert difference == 0, (
                "Different amount of nodes in tree than widget. "
                f"difference={difference} tree={rendered_tree[1:]} tabs={tabs}"
            )

        # Return dummy entries for now. Once we finish whatever operation is
        # causing the current irregularity we should get proper values.
        fields["tree"] = ""
        fields["collapsed"] = ""
        return fields

    def update_tree_tab_positions(self):
        """Update tab positions according to the tree structure."""
        nodes = self.tree_root.traverse(render_collapsed=False)
        for idx, node in enumerate(nodes):
            if idx > 0:
                cur_idx = self.indexOf(node.value)
                self.tabBar().moveTab(cur_idx, idx-1)

    def update_tree_tab_visibility(self):
        """Hide collapsed tabs and show uncollapsed ones.

        Sync the internal tree to the tabs the user can actually see.
        """
        for node in self.tree_root.traverse():
            if node.value is None:
                continue
            if any(ancestor.collapsed for ancestor in node.path[:-1]):
                if self.indexOf(node.value) != -1:
                    # node should be hidden but is shown
                    cur_tab = node.value
                    idx = self.indexOf(cur_tab)
                    if idx != -1:
                        self.removeTab(idx)
            else:
                if self.indexOf(node.value) == -1:
                    # node should be shown but is hidden
                    parent = node.parent
                    tab = node.value
                    name = tab.title()
                    icon = tab.icon()
                    if node.parent is not None:
                        parent_idx = self.indexOf(node.parent.value)
                    self.insertTab(parent_idx + 1, tab, icon, name)
                    tab.node.parent = parent  # insertTab resets node

    def tree_tab_update(self):
        """Update titles and positions."""
        with self._disable_tab_title_updates():
            self.update_tree_tab_visibility()
            self.update_tree_tab_positions()
        self.update_tab_titles()
