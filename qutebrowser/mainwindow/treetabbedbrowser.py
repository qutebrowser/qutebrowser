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

    def _hierarchy_post_remove(self, cur_node):
        node_parent = cur_node.parent

        if node_parent:
            node_siblings = list(node_parent.children)
            node_children = cur_node.children

            if node_children:
                next_node = node_children[0]

                # prvni node se stane parentem pro ostatní děti
                for n in node_children[1:]:
                    n.parent = next_node

                # swap nodes
                node_idx = node_siblings.index(cur_node)
                node_siblings[node_idx] = next_node

                node_parent.children = tuple(node_siblings)
                cur_node.children = ()

            cur_node.parent = None

    def _remove_tab(self, tab, *, add_undo=True, new_undo=True, crashed=False):
        super()._remove_tab(tab, add_undo=add_undo, new_undo=new_undo,
                            crashed=crashed)
        self._hierarchy_post_remove(tab.node)

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
            children = [n.uid for n in node.children]
            local_idx = node.index
            entry = UndoEntry(tab.url(), history_data, idx,
                              tab.data.pinned,
                              uid, parent_uid, children, local_idx)

            if new_undo or not self._undo_stack:
                self._undo_stack.append([entry])
            else:
                self._undo_stack[-1].append(entry)

    def undo(self):
        """Undo removing of a tab or tabs."""
        # TODO find a way to remove dupe code
        # probably by getting entries from undo stack, THEN calling super
        # then post-processing the entries
        # Remove unused tab which may be created after the last tab is closed
        last_close = config.val.tabs.last_close
        use_current_tab = False
        if last_close in ['blank', 'startpage', 'default-page']:
            only_one_tab_open = self.widget.count() == 1
            no_history = len(self.widget.widget(0).history) == 1
            urls = {
                'blank': QUrl('about:blank'),
                'startpage': config.val.url.start_pages[0],
                'default-page': config.val.url.default_page,
            }
            first_tab_url = self.widget.widget(0).url()
            last_close_urlstr = urls[last_close].toString().rstrip('/')
            first_tab_urlstr = first_tab_url.toString().rstrip('/')
            last_close_url_used = first_tab_urlstr == last_close_urlstr
            use_current_tab = (only_one_tab_open and no_history and
                               last_close_url_used)

        for entry in reversed(self._undo_stack.pop()):
            if use_current_tab:
                newtab = self.widget.widget(0)
                use_current_tab = False
            else:
                newtab = self.tabopen(background=False, idx=entry.index)
                if (config.val.tabs.tree_tabs and
                        entry.uid is not None and
                        entry.parent_node_uid is not None):
                    root = self.widget.tree_root
                    uid = entry.uid
                    parent_uid = entry.parent_node_uid
                    parent_node = root.get_descendent_by_uid(parent_uid)

                    children = []
                    for child_uid in entry.children_node_uids:
                        child_node = root.get_descendent_by_uid(child_uid)
                        children.append(child_node)
                    newtab.node.parent = None  # Remove the node from the tree
                    newtab.node = notree.Node(newtab, parent_node,
                                              children, uid)

                    # correctly reposition the tab
                    local_idx = entry.local_index
                    new_siblings = list(newtab.node.parent.children)
                    new_siblings.remove(newtab.node)
                    new_siblings.insert(local_idx, newtab.node)
                    newtab.node.parent.children = new_siblings

                    self.widget.tree_tab_update()

            newtab.history.private_api.deserialize(entry.history)
            self.widget.set_tab_pinned(newtab, entry.pinned)

    def _tree_tab_pre_open(self, tab, related):
        """Set tab's parent and position relatively to its siblings/root.

        If related is True, the tab is placed as the last children of current
        tab.
        Else, the tab is placed as a children of tree_root, and its placement
        relatively to its siblings follows tabs.new_position.unrelated config
        setting.

        Args:
            tab: The AbstractTab that is about to be opened
            related: Whether the tab is related to the current one or not

        """
        cur_tab = self.widget.currentWidget()
        tab.node.parent = self.widget.tree_root
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

        self.widget.tree_tab_update()

    @pyqtSlot('QUrl')
    @pyqtSlot('QUrl', bool)
    @pyqtSlot('QUrl', bool, bool)
    def tabopen(self, url=None, background=None, related=True, idx=None, *,
                ignore_tabs_are_windows=False):
        """Open a new tab with a given URL.

        Inner logic for open-tab and open-tab-bg.
        Also connect all the signals we need to _filter_signals.

        Args:
            url: The URL to open as QUrl or None for an empty tab.
            background: Whether to open the tab in the background.
                        if None, the `tabs.background_tabs`` setting decides.
            related: Whether the tab was opened from another existing tab.
                     If this is set, the new position might be different. With
                     the default settings we handle it like Chromium does:
                         - Tabs from clicked links etc. are to the right of
                           the current (related=True).
                         - Explicitly opened tabs are at the very right
                           (related=False)
            idx: The index where the new tab should be opened.
            ignore_tabs_are_windows: If given, never open a new window, even
                                     with tabs.tabs_are_windows set.

        Return:
            The opened WebView instance.
        """
        # TODO Find a way to remove dupe code
        # probably by calling _pre_open in insertTab event listener or
        # something
        if url is not None:
            qtutils.ensure_valid(url)
        log.webview.debug("Creating new tab with URL {}, background {}, "
                          "related {}, idx {}".format(
                              url, background, related, idx))

        prev_focus = QApplication.focusWidget()

        if (config.val.tabs.tabs_are_windows and self.widget.count() > 0 and
                not ignore_tabs_are_windows):
            window = mainwindow.MainWindow(private=self.is_private)
            window.show()
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=window.win_id)
            return tabbed_browser.tabopen(url=url, background=background,
                                          related=related)

        tab = browsertab.create(win_id=self._win_id,
                                private=self.is_private,
                                parent=self.widget)
        self._connect_tab_signals(tab)

        if idx is None:
            idx = self._get_new_tab_idx(related)  # ignored by tree-tabs
        idx = self.widget.insertTab(idx, tab, "")

        log.misc.debug('\n'.join(''.join((char, repr(node))) for char, node in self.widget.tree_root.render()))

        if config.val.tabs.tree_tabs:
            self._tree_tab_pre_open(tab, related)

        if url is not None:
            tab.load_url(url)

        if background is None:
            background = config.val.tabs.background
        if background:
            # Make sure the background tab has the correct initial size.
            # With a foreground tab, it's going to be resized correctly by the
            # layout anyways.
            tab.resize(self.widget.currentWidget().size())
            self.widget.tab_index_changed.emit(self.widget.currentIndex(),
                                               self.widget.count())
            # Refocus webview in case we lost it by spawning a bg tab
            self.widget.currentWidget().setFocus()
        else:
            self.widget.setCurrentWidget(tab)
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-68076
            # Still seems to be needed with Qt 5.11.1
            tab.setFocus()

        mode = modeman.instance(self._win_id).mode
        if mode in [usertypes.KeyMode.command, usertypes.KeyMode.prompt,
                    usertypes.KeyMode.yesno]:
            # If we were in a command prompt, restore old focus
            # The above commands need to be run to switch tabs
            if prev_focus is not None:
                prev_focus.setFocus()

        tab.show()
        self.new_tab.emit(tab, idx)
        return tab
