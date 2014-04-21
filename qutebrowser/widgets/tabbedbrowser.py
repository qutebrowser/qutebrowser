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

from PyQt5.QtWidgets import QApplication, QShortcut, QSizePolicy
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt
from PyQt5.QtGui import QClipboard

import qutebrowser.utils.url as urlutils
import qutebrowser.config.config as config
import qutebrowser.commands.utils as cmdutils
from qutebrowser.widgets.tabwidget import TabWidget
from qutebrowser.widgets.browsertab import BrowserTab
from qutebrowser.browser.signalfilter import SignalFilter
from qutebrowser.browser.curcommand import CurCommandDispatcher


class TabbedBrowser(TabWidget):

    """A TabWidget with QWebViews inside.

    Provides methods to manage tabs, convenience methods to interact with the
    current tab (cur_*) and filters signals to re-emit them when they occured
    in the currently visible tab.

    For all tab-specific signals (cur_*) emitted by a tab, this happens:
       - the signal gets added to a signal_cache of the tab, so it can be
         emitted again if the current tab changes.
       - the signal gets filtered with _filter_signals and self.cur_* gets
         emitted if the signal occured in the current tab.

    Attributes:
        _url_stack: Stack of URLs of closed tabs.
        _space: Space QShortcut to avoid garbage collection
        _tabs: A list of open tabs.
        _filter: A SignalFilter instance.
        cur: A CurCommandDispatcher instance to dispatch commands to the
             current tab.

    Signals:
        cur_progress: Progress of the current tab changed (loadProgress).
        cur_load_started: Current tab started loading (loadStarted)
        cur_load_finished: Current tab finished loading (loadFinished)
        cur_statusbar_message: Current tab got a statusbar message
                               (statusBarMessage)
        cur_temp_message: Current tab needs to show a temporary message.
        cur_url_changed: Current URL changed (urlChanged)
        cur_link_hovered: Link hovered in current tab (linkHovered)
        cur_scroll_perc_changed: Scroll percentage of current tab changed.
                                 arg 1: x-position in %.
                                 arg 2: y-position in %.
        hint_strings_updated: Hint strings were updated.
                              arg: A list of hint strings.
        set_mode: The input mode should be changed.
                  arg: The new mode as a string.
        keypress: A key was pressed.
                  arg: The QKeyEvent leading to the keypress.
        shutdown_complete: The shuttdown is completed.
        quit: The last tab was closed, quit application.
        resized: Emitted when the browser window has resized, so the completion
                 widget can adjust its size to it.
                 arg: The new size.
    """

    cur_progress = pyqtSignal(int)
    cur_load_started = pyqtSignal()
    cur_load_finished = pyqtSignal(bool)
    cur_temp_message = pyqtSignal(str)
    cur_statusbar_message = pyqtSignal(str)
    cur_url_changed = pyqtSignal('QUrl')
    cur_link_hovered = pyqtSignal(str, str, str)
    cur_scroll_perc_changed = pyqtSignal(int, int)
    hint_strings_updated = pyqtSignal(list)
    set_cmd_text = pyqtSignal(str)
    set_mode = pyqtSignal(str)
    keypress = pyqtSignal('QKeyEvent')
    shutdown_complete = pyqtSignal()
    quit = pyqtSignal()
    resized = pyqtSignal('QRect')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(lambda idx:
                                    self.widget(idx).signal_cache.replay())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tabs = []
        self._url_stack = []
        self._space = QShortcut(self)
        self._space.setKey(Qt.Key_Space)
        self._space.setContext(Qt.WidgetWithChildrenShortcut)
        self._space.activated.connect(lambda: self.cur.scroll_page(0, 1))
        self._filter = SignalFilter(self)
        self.cur = CurCommandDispatcher(self)
        self.cur.temp_message.connect(self.cur_temp_message)

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
            return self.widget(count - 1)
        else:
            return None

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update tab config when config was changed."""
        super().on_config_changed(section, option)
        for tab in self._tabs:
            tab.on_config_changed(section, option)

    def _titleChanged_handler(self, text):
        """Set the title of a tab.

        Slot for the titleChanged signal of any tab.

        Args:
            text: The text to set.
        """
        logging.debug('title changed to "{}"'.format(text))
        if text:
            self.setTabText(self.indexOf(self.sender()), text)
        else:
            logging.debug('ignoring title change')

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
        for tabidx in range(tabcount):
            logging.debug("Shutting down tab {}/{}".format(tabidx, tabcount))
            tab = self.widget(tabidx)
            tab.shutdown(callback=partial(self._cb_tab_shutdown, tab))

    @cmdutils.register(instance='mainwindow.tabs')
    def tabclose(self, count=None):
        """Close the current/[count]th tab.

        Command handler for :close.

        Args:
            count: The tab index to close, or None

        Emit:
            quit: If last tab was closed and last_close in config is set to
                  quit.
        """
        idx = self.currentIndex() if count is None else count - 1
        tab = self.cntwidget(count)
        if tab is None:
            return
        last_close = config.get('tabbar', 'last_close')
        if self.count() > 1:
            # FIXME maybe we actually should store the webview objects here
            self._url_stack.append(tab.url())
            self.removeTab(idx)
            tab.shutdown(callback=partial(self._cb_tab_shutdown, tab))
        elif last_close == 'quit':
            self.quit.emit()
        elif last_close == 'blank':
            tab.openurl('about:blank')

    @cmdutils.register(instance='mainwindow.tabs', maxsplit=0)
    def tabopen(self, url):
        """Open a new tab with a given url.

        Also connect all the signals we need to _filter_signals.

        Args:
            url: The URL to open.
        """
        logging.debug("Opening {}".format(url))
        url = urlutils.qurl(url)
        tab = BrowserTab(self)
        self._tabs.append(tab)
        self.addTab(tab, urlutils.urlstring(url))
        self.setCurrentWidget(tab)
        tab.linkHovered.connect(self._filter.create(self.cur_link_hovered))
        tab.loadProgress.connect(self._filter.create(self.cur_progress))
        tab.loadFinished.connect(self._filter.create(self.cur_load_finished))
        tab.loadStarted.connect(lambda:  # pylint: disable=unnecessary-lambda
                                self.sender().signal_cache.clear())
        tab.loadStarted.connect(self._filter.create(self.cur_load_started))
        tab.statusBarMessage.connect(
            self._filter.create(self.cur_statusbar_message))
        tab.scroll_pos_changed.connect(
            self._filter.create(self.cur_scroll_perc_changed))
        tab.temp_message.connect(self._filter.create(self.cur_temp_message))
        tab.urlChanged.connect(self._filter.create(self.cur_url_changed))
        tab.titleChanged.connect(self._titleChanged_handler)
        tab.hintmanager.hint_strings_updated.connect(self.hint_strings_updated)
        tab.hintmanager.set_mode.connect(self.set_mode)
        # FIXME sometimes this doesn't load
        tab.show()
        tab.open_tab.connect(self.tabopen)
        tab.openurl(url)

    @cmdutils.register(instance='mainwindow.tabs', hide=True)
    def tabopencur(self):
        """Set the statusbar to :tabopen and the current URL.

        Emit:
            set_cmd_text prefilled with :tabopen $URL
        """
        url = urlutils.urlstring(self.currentWidget().url())
        self.set_cmd_text.emit(':tabopen ' + url)

    @cmdutils.register(instance='mainwindow.tabs', hide=True)
    def opencur(self):
        """Set the statusbar to :open and the current URL.

        Emit:
            set_cmd_text prefilled with :open $URL
        """
        url = urlutils.urlstring(self.currentWidget().url())
        self.set_cmd_text.emit(':open ' + url)

    @cmdutils.register(instance='mainwindow.tabs', name='undo')
    def undo_close(self):
        """Switch to the previous tab, or skip [count] tabs.

        Command handler for :undo.
        """
        if self._url_stack:
            self.tabopen(self._url_stack.pop())

    @cmdutils.register(instance='mainwindow.tabs', name='tabprev')
    def switch_prev(self, count=1):
        """Switch to the ([count]th) previous tab.

        Command handler for :tabprev.

        Args:
            count: How many tabs to switch back.
        """
        idx = self.currentIndex()
        if idx - count >= 0:
            self.setCurrentIndex(idx - count)
        else:
            # FIXME display message or wrap
            pass

    @cmdutils.register(instance='mainwindow.tabs', name='tabnext')
    def switch_next(self, count=1):
        """Switch to the next tab, or skip [count] tabs.

        Command handler for :tabnext.

        Args:
            count: How many tabs to switch forward.
        """
        idx = self.currentIndex()
        if idx + count < self.count():
            self.setCurrentIndex(idx + count)
        else:
            # FIXME display message or wrap
            pass

    @cmdutils.register(instance='mainwindow.tabs')
    def paste(self, sel=False):
        """Open a page from the clipboard.

        Command handler for :paste.

        Args:
            sel: True to use primary selection, False to use clipboard
        """
        # FIXME what happens for invalid URLs?
        clip = QApplication.clipboard()
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        url = clip.text(mode)
        logging.debug("Clipboard contained: '{}'".format(url))
        self.cur.openurl(url)

    @cmdutils.register(instance='mainwindow.tabs')
    def tabpaste(self, sel=False):
        """Open a page from the clipboard in a new tab.

        Command handler for :paste.

        Args:
            sel: True to use primary selection, False to use clipboard
        """
        # FIXME what happens for invalid URLs?
        clip = QApplication.clipboard()
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        url = clip.text(mode)
        logging.debug("Clipboard contained: '{}'".format(url))
        self.tabopen(url)

    def keyPressEvent(self, e):
        """Extend TabWidget (QWidget)'s keyPressEvent to emit a signal.

        Args:
            e: The QKeyPressEvent

        Emit:
            keypress: Always emitted.
        """
        self.keypress.emit(e)
        super().keyPressEvent(e)

    def resizeEvent(self, e):
        """Extend resizeEvent of QWidget to emit a resized signal afterwards.

        Args:
            e: The QResizeEvent

        Emit:
            resize: Always emitted.
        """
        super().resizeEvent(e)
        self.resized.emit(self.geometry())
