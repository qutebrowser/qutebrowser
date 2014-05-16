# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""The main tabbed browser widget."""

import logging
from functools import partial

from PyQt5.QtWidgets import QApplication, QSizePolicy
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QSize
from PyQt5.QtGui import QClipboard

import qutebrowser.utils.url as urlutils
import qutebrowser.utils.message as message
import qutebrowser.config.config as config
import qutebrowser.commands.utils as cmdutils
from qutebrowser.widgets._tabwidget import TabWidget, EmptyTabIcon
from qutebrowser.widgets.webview import WebView
from qutebrowser.browser.signalfilter import SignalFilter
from qutebrowser.browser.curcommand import CurCommandDispatcher
from qutebrowser.commands.exceptions import CommandError


class TabbedBrowser(TabWidget):

    """A TabWidget with QWebViews inside.

    Provides methods to manage tabs, convenience methods to interact with the
    current tab (cur_*) and filters signals to re-emit them when they occured
    in the currently visible tab.

    For all tab-specific signals (cur_*) emitted by a tab, this happens:
       - the signal gets filtered with _filter_signals and self.cur_* gets
         emitted if the signal occured in the current tab.

    Attributes:
        _url_stack: Stack of URLs of closed tabs.
        _tabs: A list of open tabs.
        _filter: A SignalFilter instance.
        cur: A CurCommandDispatcher instance to dispatch commands to the
             current tab.
        last_focused: The tab which was focused last.
        now_focused: The tab which is focused now.

    Signals:
        cur_progress: Progress of the current tab changed (loadProgress).
        cur_load_started: Current tab started loading (loadStarted)
        cur_load_finished: Current tab finished loading (loadFinished)
        cur_statusbar_message: Current tab got a statusbar message
                               (statusBarMessage)
        cur_url_text_changed: Current URL text changed.
        cur_link_hovered: Link hovered in current tab (linkHovered)
        cur_scroll_perc_changed: Scroll percentage of current tab changed.
                                 arg 1: x-position in %.
                                 arg 2: y-position in %.
        cur_load_status_changed: Loading status of current tab changed.
        hint_strings_updated: Hint strings were updated.
                              arg: A list of hint strings.
        shutdown_complete: The shuttdown is completed.
        quit: The last tab was closed, quit application.
        resized: Emitted when the browser window has resized, so the completion
                 widget can adjust its size to it.
                 arg: The new size.
    """

    cur_progress = pyqtSignal(int)
    cur_load_started = pyqtSignal()
    cur_load_finished = pyqtSignal(bool)
    cur_statusbar_message = pyqtSignal(str)
    cur_url_text_changed = pyqtSignal(str)
    cur_link_hovered = pyqtSignal(str, str, str)
    cur_scroll_perc_changed = pyqtSignal(int, int)
    cur_load_status_changed = pyqtSignal(str)
    hint_strings_updated = pyqtSignal(list)
    shutdown_complete = pyqtSignal()
    quit = pyqtSignal()
    resized = pyqtSignal('QRect')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabCloseRequested.connect(self.on_tab_close_requested)
        self.currentChanged.connect(self.on_current_changed)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tabs = []
        self._url_stack = []
        self._filter = SignalFilter(self)
        self.cur = CurCommandDispatcher(self)
        self.last_focused = None
        self.now_focused = None
        # FIXME adjust this to font size
        self.setIconSize(QSize(12, 12))

    @property
    def widgets(self):
        """Get a list of open tab widgets.

        We don't implement this as generator so we can delete tabs while
        iterating over the list."""
        w = []
        for i in range(self.count()):
            w.append(self.widget(i))
        return w

    def _cb_tab_shutdown(self, tab):
        """Called after a tab has been shut down completely.

        Args:
            tab: The tab object which has been shut down.

        Emit:
            shutdown_complete: When the tab shutdown is done completely.
        """
        try:
            self._tabs.remove(tab)
        except ValueError:
            logging.exception("tab {} could not be removed".format(tab))
        logging.debug("Tabs after removing: {}".format(self._tabs))
        if not self._tabs:  # all tabs shut down
            logging.debug("Tab shutdown complete.")
            self.shutdown_complete.emit()

    def _connect_tab_signals(self, tab):
        """Set up the needed signals for tab."""
        # filtered signals
        tab.linkHovered.connect(self._filter.create(self.cur_link_hovered))
        tab.loadProgress.connect(self._filter.create(self.cur_progress))
        tab.loadFinished.connect(self._filter.create(self.cur_load_finished))
        tab.loadStarted.connect(self._filter.create(self.cur_load_started))
        tab.statusBarMessage.connect(
            self._filter.create(self.cur_statusbar_message))
        tab.scroll_perc_changed.connect(
            self._filter.create(self.cur_scroll_perc_changed))
        tab.url_text_changed.connect(
            self._filter.create(self.cur_url_text_changed))
        tab.url_text_changed.connect(self.on_url_text_changed)
        tab.load_status_changed.connect(
            self._filter.create(self.cur_load_status_changed))
        # hintmanager
        tab.hintmanager.hint_strings_updated.connect(self.hint_strings_updated)
        tab.hintmanager.openurl.connect(self.cur.openurl_slot)
        # misc
        tab.titleChanged.connect(self.on_title_changed)
        tab.iconChanged.connect(self.on_icon_changed)
        tab.page().mainFrame().loadStarted.connect(partial(
            self.on_load_started, tab))

    def _close_tab(self, tab_or_idx):
        """Close a tab with either index or tab given.

        Args:
            tab_or_index: Either the QWebView to be closed or an index.
        """
        try:
            idx = int(tab_or_idx)
        except TypeError:
            tab = tab_or_idx
            idx = self.indexOf(tab_or_idx)
            if idx == -1:
                raise ValueError("tab {} is not contained in "
                                 "TabbedWidget!".format(tab))
        else:
            tab = self.widget(idx)
            if tab is None:
                raise ValueError("invalid index {}!".format(idx))
        last_close = config.get('tabbar', 'last-close')
        if self.count() > 1:
            url = tab.url()
            if not url.isEmpty():
                self._url_stack.append(url)
            self.removeTab(idx)
            tab.shutdown(callback=partial(self._cb_tab_shutdown, tab))
        elif last_close == 'quit':
            self.quit.emit()
        elif last_close == 'blank':
            tab.openurl('about:blank')

    @pyqtSlot(int)
    def on_tab_close_requested(self, idx):
        """Close a tab via an index."""
        self._close_tab(idx)

    def _tab_move_absolute(self, idx):
        """Get an index for moving a tab absolutely.

        Args:
            idx: The index to get, as passed as count.
        """
        if idx is None:
            return 0
        elif idx == 0:
            return self.count() - 1
        else:
            return idx - 1

    def _tab_move_relative(self, direction, delta):
        """Get an index for moving a tab relatively.

        Args:
            direction: + or - for relative moving, None for absolute.
            delta: Delta to the current tab.
        """
        if delta is None:
            raise ValueError
        if direction == '-':
            return self.currentIndex() - delta
        elif direction == '+':
            return self.currentIndex() + delta

    @pyqtSlot(str, bool)
    def tabopen(self, url=None, background=None):
        """Open a new tab with a given URL.

        Inner logic for open-tab and open-tab-bg.
        Also connect all the signals we need to _filter_signals.

        Args:
            url: The URL to open.
            background: Whether to open the tab in the background.
                        if None, the background-tabs setting decides.

        Return:
            The opened WebView instance.
        """
        logging.debug("Creating new tab with URL {}".format(url))
        tab = WebView(self)
        self._connect_tab_signals(tab)
        self._tabs.append(tab)
        self.addTab(tab, "")
        if url is not None:
            url = urlutils.qurl(url)
            tab.openurl(url)
        if background is None:
            background = config.get('general', 'background-tabs')
        if not background:
            self.setCurrentWidget(tab)
        tab.show()
        return tab

    def cntwidget(self, count=None):
        """Return a widget based on a count/idx.

        Args:
            count: The tab index, or None.

        Return:
            The current widget if count is None.
            The widget with the given tab ID if count is given.
            None if no widget was found.
        """
        if count is None:
            return self.currentWidget()
        elif 1 <= count <= self.count():
            cmdutils.check_overflow(count + 1, 'int')
            return self.widget(count - 1)
        else:
            return None

    def shutdown(self):
        """Try to shut down all tabs cleanly.

        Emit:
            shutdown_complete if the shutdown completed successfully.
        """
        try:
            self.currentChanged.disconnect()
        except TypeError:
            pass
        tabcount = self.count()
        if tabcount == 0:
            logging.debug("No tabs -> shutdown complete")
            self.shutdown_complete.emit()
            return
        for tab in self.widgets:
            tab.shutdown(callback=partial(self._cb_tab_shutdown, tab))

    @cmdutils.register(instance='mainwindow.tabs', name='tab-close')
    def tabclose(self, count=None):
        """Close the current/[count]th tab.

        Command handler for :tab-close.

        Args:
            count: The tab index to close, or None

        Emit:
            quit: If last tab was closed and last-close in config is set to
                  quit.
        """
        tab = self.cntwidget(count)
        if tab is None:
            return
        self._close_tab(tab)

    @cmdutils.register(instance='mainwindow.tabs')
    def tab_only(self):
        """Close all tabs except for the current one."""
        for tab in self.widgets:
            if tab is self.currentWidget():
                continue
            self._close_tab(tab)

    @cmdutils.register(instance='mainwindow.tabs', split=False)
    def open_tab(self, url):
        """Open a new tab with a given url."""
        self.tabopen(url, background=False)

    @cmdutils.register(instance='mainwindow.tabs', split=False)
    def open_tab_bg(self, url):
        """Open a new tab in background."""
        self.tabopen(url, background=True)

    @cmdutils.register(instance='mainwindow.tabs', hide=True)
    def open_tab_cur(self):
        """Set the statusbar to :tabopen and the current URL."""
        url = urlutils.urlstring(self.currentWidget().url())
        message.set_cmd_text(':open-tab ' + url)

    @cmdutils.register(instance='mainwindow.tabs', hide=True)
    def open_cur(self):
        """Set the statusbar to :open and the current URL."""
        url = urlutils.urlstring(self.currentWidget().url())
        message.set_cmd_text(':open ' + url)

    @cmdutils.register(instance='mainwindow.tabs', hide=True)
    def open_tab_bg_cur(self):
        """Set the statusbar to :tabopen-bg and the current URL."""
        url = urlutils.urlstring(self.currentWidget().url())
        message.set_cmd_text(':open-tab-bg ' + url)

    @cmdutils.register(instance='mainwindow.tabs', name='undo')
    def undo_close(self):
        """Re-open a closed tab (optionally skipping [count] tabs).

        Command handler for :undo.
        """
        if self._url_stack:
            self.tabopen(self._url_stack.pop())
        else:
            raise CommandError("Nothing to undo!")

    @cmdutils.register(instance='mainwindow.tabs', name='tab-prev')
    def switch_prev(self, count=1):
        """Switch to the previous tab, or skip [count] tabs.

        Command handler for :tab-prev.

        Args:
            count: How many tabs to switch back.
        """
        newidx = self.currentIndex() - count
        if newidx >= 0:
            self.setCurrentIndex(newidx)
        elif config.get('tabbar', 'wrap'):
            self.setCurrentIndex(newidx % self.count())
        else:
            raise CommandError("First tab")

    @cmdutils.register(instance='mainwindow.tabs', name='tab-next')
    def switch_next(self, count=1):
        """Switch to the next tab, or skip [count] tabs.

        Command handler for :tab-next.

        Args:
            count: How many tabs to switch forward.
        """
        newidx = self.currentIndex() + count
        if newidx < self.count():
            self.setCurrentIndex(newidx)
        elif config.get('tabbar', 'wrap'):
            self.setCurrentIndex(newidx % self.count())
        else:
            raise CommandError("Last tab")

    @cmdutils.register(instance='mainwindow.tabs', nargs=(0, 1))
    def paste(self, sel=False, tab=False):
        """Open a page from the clipboard.

        Command handler for :paste.

        Args:
            sel: True to use primary selection, False to use clipboard
            tab: True to open in a new tab.
        """
        clip = QApplication.clipboard()
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        url = clip.text(mode)
        if not url:
            raise CommandError("Clipboard is empty.")
        logging.debug("Clipboard contained: '{}'".format(url))
        if tab:
            self.tabopen(url)
        else:
            self.cur.openurl(url)

    @cmdutils.register(instance='mainwindow.tabs')
    def paste_tab(self, sel=False):
        """Open a page from the clipboard in a new tab.

        Command handler for :paste.

        Args:
            sel: True to use primary selection, False to use clipboard
        """
        self.paste(sel, True)

    @cmdutils.register(instance='mainwindow.tabs')
    def tab_focus(self, index=None, count=None):
        """Select the tab given as argument/[count].

        Args:
            index: The tab index to focus, starting with 1.
        """
        try:
            idx = cmdutils.arg_or_count(index, count, default=1,
                                        countzero=self.count())
        except ValueError as e:
            raise CommandError(e)
        cmdutils.check_overflow(idx + 1, 'int')
        if 1 <= idx <= self.count():
            self.setCurrentIndex(idx - 1)
        else:
            raise CommandError("There's no tab with index {}!".format(idx))

    @cmdutils.register(instance='mainwindow.tabs')
    def tab_move(self, direction=None, count=None):
        """Move the current tab.

        Args:
            direction: + or - for relative moving, None for absolute.
            count: If moving absolutely: New position (or first).
                   If moving relatively: Offset.
        """
        if direction is None:
            new_idx = self._tab_move_absolute(count)
        elif direction in '+-':
            try:
                new_idx = self._tab_move_relative(direction, count)
            except ValueError:
                raise CommandError("Count must be given for relative moving!")
        else:
            raise CommandError("Invalid direction '{}'!".format(direction))
        if not 0 <= new_idx < self.count():
            raise CommandError("Can't move tab to position {}!".format(
                new_idx))
        tab = self.currentWidget()
        cur_idx = self.currentIndex()
        icon = self.tabIcon(cur_idx)
        label = self.tabText(cur_idx)
        cmdutils.check_overflow(cur_idx, 'int')
        cmdutils.check_overflow(new_idx, 'int')
        self.removeTab(cur_idx)
        self.insertTab(new_idx, tab, icon, label)
        self.setCurrentIndex(new_idx)

    @cmdutils.register(instance='mainwindow.tabs')
    def tab_focus_last(self):
        """Select the tab which was last focused."""
        idx = self.indexOf(self.last_focused)
        if idx == -1:
            raise CommandError("Last focused tab vanished!")
        self.setCurrentIndex(idx)

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update tab config when config was changed."""
        super().on_config_changed(section, option)
        for tab in self._tabs:
            tab.on_config_changed(section, option)
        if (section, option) == ('tabbar', 'show-favicons'):
            show = config.get('tabbar', 'show-favicons')
            for i, tab in enumerate(self.widgets):
                if show:
                    self.setTabIcon(i, tab.icon())
                else:
                    self.setTabIcon(i, EmptyTabIcon())

    @pyqtSlot()
    def on_load_started(self, tab):
        """Clear icon when a tab started loading.

        Args:
            tab: The tab where the signal belongs to.
        """
        self.setTabIcon(self.indexOf(tab), EmptyTabIcon())

    @pyqtSlot(str)
    def on_title_changed(self, text):
        """Set the title of a tab.

        Slot for the titleChanged signal of any tab.

        Args:
            text: The text to set.
        """
        logging.debug("title changed to '{}'".format(text))
        if text:
            self.setTabText(self.indexOf(self.sender()), text)
        else:
            logging.debug("ignoring title change")

    @pyqtSlot(str)
    def on_url_text_changed(self, url):
        """Set the new URL as title if there's no title yet."""
        idx = self.indexOf(self.sender())
        if not self.tabText(idx):
            self.setTabText(idx, url)

    @pyqtSlot()
    def on_icon_changed(self):
        """Set the icon of a tab.

        Slot for the iconChanged signal of any tab.
        """
        if not config.get('tabbar', 'show-favicons'):
            return
        tab = self.sender()
        self.setTabIcon(self.indexOf(tab), tab.icon())

    @pyqtSlot(str)
    def on_mode_left(self, mode):
        """Give focus to tabs if command mode was left."""
        if mode == "command":
            self.setFocus()

    @pyqtSlot(int)
    def on_current_changed(self, idx):
        """Set last_focused when focus changed."""
        tab = self.widget(idx)
        self.last_focused = self.now_focused
        self.now_focused = tab

    def resizeEvent(self, e):
        """Extend resizeEvent of QWidget to emit a resized signal afterwards.

        Args:
            e: The QResizeEvent

        Emit:
            resize: Always emitted.
        """
        super().resizeEvent(e)
        self.resized.emit(self.geometry())
