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

"""Subclass of TabbedBrowser to provide tree-tab functionality."""

import attr

from PyQt5.QtWidgets import QSizePolicy, QWidget, QApplication
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QTimer, QUrl

from qutebrowser.config import config
from qutebrowser.mainwindow.tabbedbrowser import TabbedBrowser, UndoEntry
from qutebrowser.mainwindow.treetabwidget import TreeTabWidget
from qutebrowser.browser import browsertab
from qutebrowser.misc import notree

from PyQt5.QtGui import QIcon

from qutebrowser.keyinput import modeman
from qutebrowser.mainwindow import tabwidget, mainwindow
from qutebrowser.utils import (log, usertypes, utils, qtutils, objreg,
                               urlutils, message, jinja)


@attr.s
class TreeUndoEntry:
    """Information needed for :undo."""

    url = attr.ib()
    history = attr.ib()
    index = attr.ib()
    pinned = attr.ib()
    uid = attr.ib(None)
    parent_node_uid = attr.ib(None)
    children_node_uids = attr.ib(attr.Factory(list))
    local_index = attr.ib(None)  # index of the tab relative to its siblings

    @classmethod
    def from_node(cls, node, idx):
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
        return cls(url, history_data, idx, pinned,
                   uid, parent_uid, children, local_idx)




class TreeTabbedBrowser(TabbedBrowser):
    """Subclass of TabbedBrowser to provide tree-tab functionality."""

    def __init__(self, *, win_id, private, parent=None):
        super().__init__(win_id=win_id, private=private, parent=parent)
        self.widget = TreeTabWidget(win_id, parent=self)
        self.widget.tabCloseRequested.connect(self.on_tab_close_requested)
        self.widget.new_tab_requested.connect(self.tabopen)
        self.widget.currentChanged.connect(self.on_current_changed)
        self.cur_fullscreen_requested.connect(self.widget.tabBar().maybe_hide)
        self.widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _remove_tab(self, tab, *, add_undo=True, new_undo=True, crashed=False):
        super()._remove_tab(tab, add_undo=add_undo, new_undo=new_undo,
                            crashed=crashed)

        node = tab.node
        parent = node.parent

        if node.collapsed:
            # when node is collapsed, behave as with recursive close
            node.parent = None
        elif parent:
            siblings = list(parent.children)
            children = node.children

            if children:
                next_node = children[0]

                for n in children[1:]:
                    n.parent = next_node

                # swap nodes
                node_idx = siblings.index(node)
                siblings[node_idx] = next_node

                parent.children = tuple(siblings)
                node.children = ()

            node.parent = None

    def _add_undo_entry(self, tab, idx, new_undo):

        # TODO see if it's possible to remove duplicate code from
        # super()._add_undo_entry
        try:
            history_data = tab.history.private_api.serialize()
        except browsertab.WebTabError:
            pass  # special URL
        else:
            node = tab.node
            uid = node.uid
            parent_uid = node.parent.uid
            if not node.collapsed:
                children = [n.uid for n in node.children]
                local_idx = node.index
                entry = TreeUndoEntry(tab.url(), history_data, idx,
                                    tab.data.pinned,
                                    uid, parent_uid, children, local_idx)
                if new_undo or not self._undo_stack:
                    self._undo_stack.append([entry])
                else:
                    self._undo_stack[-1].append(entry)
            else:
                entries = []
                for descendent in node.traverse(notree.TraverseOrder.POST_R):
                    entries.append(TreeUndoEntry.from_node(descendent, 0))
                    # ensure descendent is not later saved as child as well
                    descendent.parent = None
                self._undo_stack.append(entries)





    def undo(self):
        """Undo removing of a tab or tabs."""
        # TODO find a way to remove dupe code
        # probably by getting entries from undo stack, THEN calling super
        # then post-processing the entries

        # save entries before super().undo() pops them
        entries = list(self._undo_stack[-1])
        new_tabs = super().undo()
        log.misc.debug("===========================")
        log.misc.debug([(e.uid, e.parent_node_uid, e.children_node_uids) for e in entries])

        for entry, tab in zip(reversed(entries), new_tabs):
            if not isinstance(entry, TreeUndoEntry):
                continue
            root = self.widget.tree_root
            uid = entry.uid
            parent_uid = entry.parent_node_uid
            parent_node = root.get_descendent_by_uid(parent_uid)

            children = []
            for child_uid in entry.children_node_uids:
                child_node = root.get_descendent_by_uid(child_uid)
                children.append(child_node)
            tab.node.parent = None  # Remove the node from the tree
            tab.node = notree.Node(tab, parent_node,
                                    children, uid)

            # correctly reposition the tab
            local_idx = entry.local_index
            new_siblings = list(tab.node.parent.children)
            new_siblings.remove(tab.node)
            new_siblings.insert(local_idx, tab.node)
            tab.node.parent.children = new_siblings

        self.widget.tree_tab_update()

    @pyqtSlot('QUrl')
    @pyqtSlot('QUrl', bool)
    @pyqtSlot('QUrl', bool, bool)
    def tabopen(self, url=None, background=None, related=True, idx=None, *,
                ignore_tabs_are_windows=False):

        # we save this now because super.tabopen also resets the focus
        cur_tab = self.widget.currentWidget()
        tab = super().tabopen(url, background, related, idx,
                              ignore_tabs_are_windows=ignore_tabs_are_windows)

        tab.node.parent = self.widget.tree_root
        if cur_tab is not None:
            if related:
                if tab is not cur_tab:  # check we're not opening first tab
                    tab.node.parent = cur_tab.node
            else:
                pos = config.val.tabs.new_position.unrelated
                if pos == 'first':
                    children = list(tab.node.parent.children)
                    children.insert(0, children.pop())
                    tab.node.parent.children = children
                elif pos in ['next', 'prev']:
                    diff = 1 if pos == 'next' else 0
                    root_children = list(self.widget.tree_root.children)
                    root_children.remove(tab.node)

                    cur_topmost = cur_tab.node.path[1]
                    cur_top_idx = root_children.index(cur_topmost)
                    root_children.insert(cur_top_idx + diff, tab.node)
                    self.widget.tree_root.children = root_children
        return tab
