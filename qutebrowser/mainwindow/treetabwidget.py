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

from qutebrowser.config import config
from qutebrowser.mainwindow.tabwidget import TabWidget
from qutebrowser.misc.notree import Node
from qutebrowser.utils import log


class TreeTabWidget(TabWidget):
    """Tab widget used in TabbedBrowser, with tree-functionality."""

    def __init__(self, win_id, parent=None):
        # root of the tab tree, common for all tabs in the window
        self.tree_root = Node(None)
        super().__init__(win_id, parent)

    @classmethod
    def from_tabwidget(cls, tabwidget):
        tabwidget.__class__ = cls
        tabwidget.tree_root = Node(None, uid=1)
        return tabwidget

    @classmethod
    def to_tabwidget(cls, tabwidget):
        tabwidget.__class__ = cls.__bases__[0]
        tabwidget.tree_root = None
        return tabwidget

    def _init_config(self):
        super()._init_config()
        # For tree-tabs
        self.update_tab_titles()  # Must also be called when deactivating
        if config.cache['tabs.tree_tabs']:
            # Positions matter only if enabling
            self.tree_tab_update()

    def get_tab_fields(self, idx):
        fields = super().get_tab_fields(idx)

        tab = self.widget(idx)
        fields['collapsed'] = ' [...] ' if tab.node.collapsed else ''

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
        """Update tab positions acording tree structure."""
        nodes = self.tree_root.traverse(render_collapsed=False)
        for idx, node in enumerate(nodes):
            if idx > 0:
                cur_idx = self.indexOf(node.value)
                self.tabBar().moveTab(cur_idx, idx-1)

    def tree_tab_update(self):
        self.update_tab_titles()
        self.update_tree_tab_positions()

    def tabRemoved(self, idx):
        super().tabRemoved(idx)
        if config.val.tabs.tree_tabs:
            self.tree_tab_update()
