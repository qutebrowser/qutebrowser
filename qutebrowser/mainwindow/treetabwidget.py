# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Giuseppe Stelluto (pinusc) <giuseppe@gstelluto.com>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

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
        self.tabBar().tabMoved.disconnect(  # type: ignore
            self.update_tab_titles)

    def _init_config(self):
        super()._init_config()
        # For tree-tabs
        self.update_tab_titles()  # Must also be called when deactivating
        self.tree_tab_update()

    def get_tab_fields(self, idx):
        """Add tree field data to normal tab field data."""
        fields = super().get_tab_fields(idx)

        tab = self.widget(idx)
        fields['collapsed'] = '[...] ' if tab.node.collapsed else ''

        # we remove the first two chars because every tab is child of tree
        # root and that gets rendered as well
        rendered_tree = self.tree_root.render()
        try:
            pre, _ = rendered_tree[idx+1]
            tree_prefix = pre[2:]
        except IndexError:  # window or first tab are not initialized yet
            tree_prefix = ""
            log.misc.error("tree_prefix is empty!")

        fields['tree'] = tree_prefix
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
                    parent_idx = self.indexOf(node.parent.value)
                    self.insertTab(parent_idx + 1, tab, icon, name)
                    tab.node.parent = parent  # insertTab resets node

    def tree_tab_update(self):
        """Update titles and positions."""
        self.update_tree_tab_visibility()
        self.update_tree_tab_positions()
        self.update_tab_titles()
