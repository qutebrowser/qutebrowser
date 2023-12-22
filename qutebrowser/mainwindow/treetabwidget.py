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

        # We can be called when the count of tabs in the widget is different
        # to the size of the rendered tree. This is known to happen when
        # hiding a tree group with multiple tabs in it. render() will reflect
        # the final state right away but we get called for every removal or
        # insertion from the tab widget while update_tree_tab_visibility() is
        # traversing through the tree group to update the widget.
        # There may be other cases when this happens that we would be
        # swallowing here. To avoid that, since we get called via
        # update_tab_titles() possibly it would be cleanest to add an
        # attribute to TabWidget (or a context manager) to disabled tab title
        # updates and set that while calling
        # update_tree_tab_{visibility,positions} in tree_tab_update().
        miscount = len(rendered_tree) - 1 - self.count()
        if miscount < 0:
            log.misc.error(f"Less nodes in tree than widget. Are we collapsing tabs? {idx=} {miscount=} {fields['current_url']=}")
            return fields
        elif miscount > 0:
            log.misc.error(f"More nodes in tree than widget. Are we revealing tabs? {idx=} {miscount=} {fields['current_url']=}")
            return fields

        # we remove the first two chars because every tab is child of tree
        # root and that gets rendered as well
        pre, _ = rendered_tree[idx+1]
        tree_prefix = pre[2:]
        fields['tree'] = tree_prefix

        tab = self.widget(idx)
        fields['collapsed'] = '[...] ' if tab.node.collapsed else ''

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
        self.update_tree_tab_visibility()
        self.update_tree_tab_positions()
        self.update_tab_titles()
