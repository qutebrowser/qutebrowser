# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

from functools import partial

from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QSize
from PyQt5.QtGui import QIcon

import qutebrowser.config.config as config
import qutebrowser.commands.utils as cmdutils
import qutebrowser.keyinput.modeman as modeman
import qutebrowser.utils.log as log
import qutebrowser.utils.misc as utils
from qutebrowser.widgets.tabwidget import TabWidget
from qutebrowser.widgets.webview import WebView
from qutebrowser.browser.signalfilter import SignalFilter
from qutebrowser.browser.commands import CommandDispatcher
from qutebrowser.utils.qt import qt_ensure_valid, QtValueError
from qutebrowser.commands.exceptions import CommandError
from qutebrowser.utils.usertypes import KeyMode


class TabbedBrowser(TabWidget):

    """A TabWidget with QWebViews inside.

    Provides methods to manage tabs, convenience methods to interact with the
    current tab (cur_*) and filters signals to re-emit them when they occured
    in the currently visible tab.

    For all tab-specific signals (cur_*) emitted by a tab, this happens:
       - the signal gets filtered with _filter_signals and self.cur_* gets
         emitted if the signal occured in the current tab.

    Attributes:
        _tabs: A list of open tabs.
        _filter: A SignalFilter instance.
        url_stack: Stack of URLs of closed tabs.
        cmd: A TabCommandDispatcher instance.
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
        start_download: Emitted when any tab wants to start downloading
                        something.
        current_tab_changed: The current tab changed to the emitted WebView.
        title_changed: Emitted when the application title should be changed.
                       arg: The new title as string.
        download_get: Emitted when a QUrl should be downloaded.
    """

    cur_progress = pyqtSignal(int)
    cur_load_started = pyqtSignal()
    cur_load_finished = pyqtSignal(bool)
    cur_statusbar_message = pyqtSignal(str)
    cur_url_text_changed = pyqtSignal(str)
    cur_link_hovered = pyqtSignal(str, str, str)
    cur_scroll_perc_changed = pyqtSignal(int, int)
    cur_load_status_changed = pyqtSignal(str)
    start_download = pyqtSignal('QNetworkReply*')
    download_get = pyqtSignal('QUrl', 'QWebPage')
    hint_strings_updated = pyqtSignal(list)
    shutdown_complete = pyqtSignal()
    quit = pyqtSignal()
    resized = pyqtSignal('QRect')
    got_cmd = pyqtSignal(str)
    current_tab_changed = pyqtSignal(WebView)
    title_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabCloseRequested.connect(self.on_tab_close_requested)
        self.currentChanged.connect(self.on_current_changed)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tabs = []
        self.url_stack = []
        self._filter = SignalFilter(self)
        self.cmd = CommandDispatcher(self)
        self.last_focused = None
        self.now_focused = None
        # FIXME adjust this to font size
        self.setIconSize(QSize(12, 12))

    def __repr__(self):
        return '<{} with {} tabs>'.format(self.__class__.__name__,
                                          self.count())

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
            log.destroy.exception("tab {} could not be removed")
        log.destroy.debug("Tabs after removing: {}".format(self._tabs))
        if not self._tabs:  # all tabs shut down
            log.destroy.debug("Tab shutdown complete.")
            self.shutdown_complete.emit()

    def _connect_tab_signals(self, tab):
        """Set up the needed signals for tab."""
        page = tab.page()
        frame = page.mainFrame()
        # filtered signals
        tab.linkHovered.connect(
            self._filter.create(self.cur_link_hovered, tab))
        tab.loadProgress.connect(
            self._filter.create(self.cur_progress, tab))
        frame.loadFinished.connect(
            self._filter.create(self.cur_load_finished, tab))
        frame.loadStarted.connect(
            self._filter.create(self.cur_load_started, tab))
        tab.statusBarMessage.connect(
            self._filter.create(self.cur_statusbar_message, tab))
        tab.scroll_pos_changed.connect(
            self._filter.create(self.cur_scroll_perc_changed, tab))
        tab.url_text_changed.connect(
            self._filter.create(self.cur_url_text_changed, tab))
        tab.load_status_changed.connect(
            self._filter.create(self.cur_load_status_changed, tab))
        tab.url_text_changed.connect(partial(self.on_url_text_changed, tab))
        # hintmanager
        tab.hintmanager.hint_strings_updated.connect(self.hint_strings_updated)
        tab.hintmanager.download_get.connect(self.download_get)
        tab.hintmanager.openurl.connect(self.openurl)
        self.cur_load_started.connect(self.on_cur_load_started)
        # downloads
        page.unsupportedContent.connect(self.start_download)
        page.start_download.connect(self.start_download)
        # misc
        tab.titleChanged.connect(partial(self.on_title_changed, tab))
        tab.iconChanged.connect(partial(self.on_icon_changed, tab))
        tab.loadProgress.connect(partial(self.on_load_progress, tab))
        frame.loadFinished.connect(partial(self.on_load_finished, tab))
        frame.loadStarted.connect(partial(self.on_load_started, tab))
        page.windowCloseRequested.connect(
            partial(self.on_window_close_requested, tab))

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

    def current_url(self):
        """Get the URL of the current tab.

        Intended to be used from command handlers.

        Return:
            The current URL as QUrl.

        Raise:
            CommandError if the current URL is invalid.
        """
        url = self.currentWidget().url()
        try:
            qt_ensure_valid(url)
        except QtValueError as e:
            msg = "Current URL is invalid"
            if e.reason:
                msg += " ({})".format(e.reason)
            msg += "!"
            raise CommandError(msg)
        return url

    def shutdown(self):
        """Try to shut down all tabs cleanly.

        Emit:
            shutdown_complete if the shutdown completed successfully.
        """
        try:
            self.currentChanged.disconnect()
        except TypeError as e:
            log.destroy.debug("Error while shutting down tabs: {}: {}".format(
                e.__class__.__name__, e))
        tabcount = self.count()
        if tabcount == 0:
            log.destroy.debug("No tabs -> shutdown complete")
            self.shutdown_complete.emit()
            return
        for tab in self.widgets:
            tab.shutdown(callback=partial(self._cb_tab_shutdown, tab))

    def close_tab(self, tab_or_idx):
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
        if tab is self.now_focused:
            self.now_focused = None
        if tab is self.last_focused:
            self.last_focused = None
        last_close = config.get('tabbar', 'last-close')
        if self.count() > 1:
            url = tab.url()
            if not url.isEmpty():
                qt_ensure_valid(url)
                self.url_stack.append(url)
            tab.shutdown(callback=partial(self._cb_tab_shutdown, tab))
            log.destroy.debug("Removing tab {}/{}".format(idx, tab))
            self.removeTab(idx)
        elif last_close == 'quit':
            self.quit.emit()
        elif last_close == 'blank':
            tab.openurl('about:blank')

    @pyqtSlot('QUrl', bool)
    def openurl(self, url, newtab):
        """Open a URL, used as a slot.

        Args:
            url: The URL to open as QUrl.
            newtab: True to open URL in a new tab, False otherwise.
        """
        qt_ensure_valid(url)
        if newtab:
            self.tabopen(url, background=False)
        else:
            self.currentWidget().openurl(url)

    @pyqtSlot(int)
    def on_tab_close_requested(self, idx):
        """Close a tab via an index."""
        self.close_tab(idx)

    @pyqtSlot(WebView)
    def on_window_close_requested(self, widget):
        """Close a tab with a widget given."""
        self.close_tab(widget)

    @pyqtSlot('QUrl', bool)
    def tabopen(self, url=None, background=None):
        """Open a new tab with a given URL.

        Inner logic for open-tab and open-tab-bg.
        Also connect all the signals we need to _filter_signals.

        Args:
            url: The URL to open as QUrl or None for an empty tab.
            background: Whether to open the tab in the background.
                        if None, the background-tabs setting decides.

        Return:
            The opened WebView instance.
        """
        if url is not None:
            qt_ensure_valid(url)
        log.webview.debug("Creating new tab with URL {}".format(url))
        tab = WebView(self)
        self._connect_tab_signals(tab)
        self._tabs.append(tab)
        self.addTab(tab, "")
        if url is not None:
            tab.openurl(url)
        if background is None:
            background = config.get('general', 'background-tabs')
        if not background:
            self.setCurrentWidget(tab)
        tab.show()
        return tab

    @pyqtSlot(str, int)
    def search(self, text, flags):
        """Search for text in the current page.

        Args:
            text: The text to search for.
            flags: The QWebPage::FindFlags.
        """
        self.currentWidget().findText(text, flags)

    @pyqtSlot(str)
    def handle_hint_key(self, keystr):
        """Handle a new hint keypress."""
        self.currentWidget().hintmanager.handle_partial_key(keystr)

    @pyqtSlot(str)
    def fire_hint(self, keystr):
        """Fire a completed hint."""
        self.currentWidget().hintmanager.fire(keystr)

    @pyqtSlot(str)
    def filter_hints(self, filterstr):
        """Filter displayed hints."""
        self.currentWidget().hintmanager.filter_hints(filterstr)

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
                    self.setTabIcon(i, QIcon())

    @pyqtSlot()
    def on_load_started(self, tab):
        """Clear icon when a tab started loading.

        Args:
            tab: The tab where the signal belongs to.
        """
        idx = self.indexOf(tab)
        if idx == -1:
            # We can get signals for tabs we already deleted...
            log.webview.debug("Got invalid tab {}!".format(tab))
            return

    @pyqtSlot()
    def on_cur_load_started(self):
        """Leave insert/hint mode when loading started."""
        modeman.maybe_leave(KeyMode.insert, 'load started')
        modeman.maybe_leave(KeyMode.hint, 'load started')

    @pyqtSlot(WebView, str)
    def on_title_changed(self, tab, text):
        """Set the title of a tab.

        Slot for the titleChanged signal of any tab.

        Args:
            tab: The WebView where the title was changed.
            text: The text to set.
        """
        log.webview.debug("title changed to '{}'".format(text))
        if text:
            idx = self.indexOf(tab)
            if idx == -1:
                # We can get signals for tabs we already deleted...
                log.webview.debug("Got invalid tab {}!".format(tab))
                return
            self.setTabText(idx, text)
            if idx == self.currentIndex():
                self.title_changed.emit('{} - qutebrowser'.format(text))
        else:
            log.webview.debug("ignoring title change")

    @pyqtSlot(WebView, str)
    def on_url_text_changed(self, tab, url):
        """Set the new URL as title if there's no title yet.

        Args:
            tab: The WebView where the title was changed.
            url: The new URL.
        """
        idx = self.indexOf(tab)
        if idx == -1:
            # We can get signals for tabs we already deleted...
            log.webview.debug("Got invalid tab {}!".format(tab))
            return
        if not self.tabText(idx):
            self.setTabText(idx, url)

    @pyqtSlot(WebView)
    def on_icon_changed(self, tab):
        """Set the icon of a tab.

        Slot for the iconChanged signal of any tab.

        Args:
            tab: The WebView where the title was changed.
        """
        if not config.get('tabbar', 'show-favicons'):
            return
        idx = self.indexOf(tab)
        if idx == -1:
            # We can get *_changed signals for tabs we already deleted...
            log.webview.debug("Got invalid tab {}!".format(tab))
            return
        self.setTabIcon(idx, tab.icon())

    @pyqtSlot(KeyMode)
    def on_mode_left(self, mode):
        """Give focus to current tab if command mode was left."""
        if mode == KeyMode.command:
            self.currentWidget().setFocus()

    @pyqtSlot(int)
    def on_current_changed(self, idx):
        """Set last_focused and leave hinting mode when focus changed."""
        tab = self.widget(idx)
        tab.setFocus()
        modeman.maybe_leave(KeyMode.hint, 'tab changed')
        self.last_focused = self.now_focused
        self.now_focused = tab
        self.current_tab_changed.emit(tab)
        self.title_changed.emit('{} - qutebrowser'.format(self.tabText(idx)))

    def on_load_progress(self, tab, perc):
        """Adjust tab indicator on load progress."""
        idx = self.indexOf(tab)
        start = config.get('colors', 'tab.indicator.start')
        stop = config.get('colors', 'tab.indicator.stop')
        system = config.get('colors', 'tab.indicator.system')
        color = utils.interpolate_color(start, stop, perc, system)
        self.tabBar().set_tab_indicator_color(idx, color)

    def on_load_finished(self, tab, ok):
        """Adjust tab indicator when loading finished."""
        idx = self.indexOf(tab)
        if ok:
            start = config.get('colors', 'tab.indicator.start')
            stop = config.get('colors', 'tab.indicator.stop')
            system = config.get('colors', 'tab.indicator.system')
            color = utils.interpolate_color(start, stop, 100, system)
        else:
            color = config.get('colors', 'tab.indicator.error')
        self.tabBar().set_tab_indicator_color(idx, color)

    def resizeEvent(self, e):
        """Extend resizeEvent of QWidget to emit a resized signal afterwards.

        Args:
            e: The QResizeEvent

        Emit:
            resize: Always emitted.
        """
        super().resizeEvent(e)
        self.resized.emit(self.geometry())
