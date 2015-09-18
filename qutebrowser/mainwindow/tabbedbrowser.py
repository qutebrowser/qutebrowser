# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import functools
import collections

from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QTimer, QUrl
from PyQt5.QtGui import QIcon

from qutebrowser.config import config
from qutebrowser.keyinput import modeman
from qutebrowser.mainwindow import tabwidget
from qutebrowser.browser import signalfilter, webview
from qutebrowser.utils import log, usertypes, utils, qtutils, objreg, urlutils


UndoEntry = collections.namedtuple('UndoEntry', ['url', 'history'])


class TabDeletedError(Exception):

    """Exception raised when _tab_index is called for a deleted tab."""


class TabbedBrowser(tabwidget.TabWidget):

    """A TabWidget with QWebViews inside.

    Provides methods to manage tabs, convenience methods to interact with the
    current tab (cur_*) and filters signals to re-emit them when they occurred
    in the currently visible tab.

    For all tab-specific signals (cur_*) emitted by a tab, this happens:
       - the signal gets filtered with _filter_signals and self.cur_* gets
         emitted if the signal occurred in the current tab.

    Attributes:
        search_text/search_flags: Search parameters which are shared between
                                  all tabs.
        _win_id: The window ID this tabbedbrowser is associated with.
        _filter: A SignalFilter instance.
        _now_focused: The tab which is focused now.
        _tab_insert_idx_left: Where to insert a new tab with
                         tabbar -> new-tab-position set to 'left'.
        _tab_insert_idx_right: Same as above, for 'right'.
        _undo_stack: List of UndoEntry namedtuples of closed tabs.
        _shutting_down: Whether we're currently shutting down.

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
        close_window: The last tab was closed, close this window.
        resized: Emitted when the browser window has resized, so the completion
                 widget can adjust its size to it.
                 arg: The new size.
        current_tab_changed: The current tab changed to the emitted WebView.
    """

    cur_progress = pyqtSignal(int)
    cur_load_started = pyqtSignal()
    cur_load_finished = pyqtSignal(bool)
    cur_statusbar_message = pyqtSignal(str)
    cur_url_text_changed = pyqtSignal(str)
    cur_link_hovered = pyqtSignal(str, str, str)
    cur_scroll_perc_changed = pyqtSignal(int, int)
    cur_load_status_changed = pyqtSignal(str)
    close_window = pyqtSignal()
    resized = pyqtSignal('QRect')
    got_cmd = pyqtSignal(str)
    current_tab_changed = pyqtSignal(webview.WebView)

    def __init__(self, win_id, parent=None):
        super().__init__(win_id, parent)
        self._win_id = win_id
        self._tab_insert_idx_left = 0
        self._tab_insert_idx_right = -1
        self._shutting_down = False
        self.tabCloseRequested.connect(self.on_tab_close_requested)
        self.currentChanged.connect(self.on_current_changed)
        self.cur_load_started.connect(self.on_cur_load_started)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._undo_stack = []
        self._filter = signalfilter.SignalFilter(win_id, self)
        self._now_focused = None
        self.search_text = None
        self.search_flags = 0
        objreg.get('config').changed.connect(self.update_favicons)
        objreg.get('config').changed.connect(self.update_window_title)
        objreg.get('config').changed.connect(self.update_tab_titles)

    def __repr__(self):
        return utils.get_repr(self, count=self.count())

    def _tab_index(self, tab):
        """Get the index of a given tab.

        Raises TabDeletedError if the tab doesn't exist anymore.
        """
        try:
            idx = self.indexOf(tab)
        except RuntimeError as e:
            log.webview.debug("Got invalid tab ({})!".format(e))
            raise TabDeletedError(e)
        if idx == -1:
            log.webview.debug("Got invalid tab (index is -1)!")
            raise TabDeletedError("index is -1!")
        return idx

    def widgets(self):
        """Get a list of open tab widgets.

        We don't implement this as generator so we can delete tabs while
        iterating over the list.
        """
        w = []
        for i in range(self.count()):
            w.append(self.widget(i))
        return w

    @config.change_filter('ui', 'window-title-format')
    def update_window_title(self):
        """Change the window title to match the current tab."""
        idx = self.currentIndex()
        if idx == -1:
            # (e.g. last tab removed)
            log.webview.debug("Not updating window title because index is -1")
            return
        tabtitle = self.page_title(idx)
        widget = self.widget(idx)

        fields = {}
        if widget.load_status == webview.LoadStatus.loading:
            fields['perc'] = '[{}%] '.format(widget.progress)
        else:
            fields['perc'] = ''
        fields['perc_raw'] = widget.progress
        fields['title'] = tabtitle
        fields['title_sep'] = ' - ' if tabtitle else ''
        fields['id'] = self._win_id
        fmt = config.get('ui', 'window-title-format')
        self.window().setWindowTitle(fmt.format(**fields))

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
        tab.url_text_changed.connect(
            functools.partial(self.on_url_text_changed, tab))
        # misc
        tab.titleChanged.connect(
            functools.partial(self.on_title_changed, tab))
        tab.iconChanged.connect(
            functools.partial(self.on_icon_changed, tab))
        tab.loadProgress.connect(
            functools.partial(self.on_load_progress, tab))
        frame.loadFinished.connect(
            functools.partial(self.on_load_finished, tab))
        frame.loadStarted.connect(
            functools.partial(self.on_load_started, tab))
        page.windowCloseRequested.connect(
            functools.partial(self.on_window_close_requested, tab))

    def current_url(self):
        """Get the URL of the current tab.

        Intended to be used from command handlers.

        Return:
            The current URL as QUrl.
        """
        widget = self.currentWidget()
        if widget is None:
            url = QUrl()
        else:
            url = widget.cur_url
        # It's possible for url to be invalid, but the caller will handle that.
        qtutils.ensure_valid(url)
        return url

    def shutdown(self):
        """Try to shut down all tabs cleanly."""
        self._shutting_down = True
        for tab in self.widgets():
            self._remove_tab(tab)

    def close_tab(self, tab):
        """Close a tab.

        Args:
            tab: The QWebView to be closed.
        """
        last_close = config.get('tabs', 'last-close')
        count = self.count()

        if last_close == 'ignore' and count == 1:
            return

        self._remove_tab(tab)

        if count == 1:  # We just closed the last tab above.
            if last_close == 'close':
                self.close_window.emit()
            elif last_close == 'blank':
                self.openurl(QUrl('about:blank'), newtab=True)
            elif last_close == 'startpage':
                url = QUrl(config.get('general', 'startpage')[0])
                self.openurl(url, newtab=True)
            elif last_close == 'default-page':
                url = config.get('general', 'default-page')
                self.openurl(url, newtab=True)

    def _remove_tab(self, tab):
        """Remove a tab from the tab list and delete it properly.

        Args:
            tab: The QWebView to be closed.
        """
        idx = self.indexOf(tab)
        if idx == -1:
            raise ValueError("tab {} is not contained in TabbedWidget!".format(
                tab))
        if tab is self._now_focused:
            self._now_focused = None
        if tab is objreg.get('last-focused-tab', None, scope='window',
                             window=self._win_id):
            objreg.delete('last-focused-tab', scope='window',
                          window=self._win_id)
        if tab.cur_url.isValid():
            history_data = qtutils.serialize(tab.history())
            entry = UndoEntry(tab.cur_url, history_data)
            self._undo_stack.append(entry)
        elif tab.cur_url.isEmpty():
            # There are some good reasons why an URL could be empty
            # (target="_blank" with a download, see [1]), so we silently ignore
            # this.
            # [1] https://github.com/The-Compiler/qutebrowser/issues/163
            pass
        else:
            # We display a warnings for URLs which are not empty but invalid -
            # but we don't return here because we want the tab to close either
            # way.
            urlutils.invalid_url_error(self._win_id, tab.cur_url, "saving tab")
        tab.shutdown()
        self.removeTab(idx)
        tab.deleteLater()

    def undo(self):
        """Undo removing of a tab."""
        url, history_data = self._undo_stack.pop()
        newtab = self.tabopen(url, background=False)
        qtutils.deserialize(history_data, newtab.history())

    @pyqtSlot('QUrl', bool)
    def openurl(self, url, newtab):
        """Open a URL, used as a slot.

        Args:
            url: The URL to open as QUrl.
            newtab: True to open URL in a new tab, False otherwise.
        """
        qtutils.ensure_valid(url)
        if newtab or self.currentWidget() is None:
            self.tabopen(url, background=False)
        else:
            self.currentWidget().openurl(url)

    @pyqtSlot(int)
    def on_tab_close_requested(self, idx):
        """Close a tab via an index."""
        tab = self.widget(idx)
        if tab is None:
            log.webview.debug("Got invalid tab {} for index {}!".format(
                tab, idx))
            return
        self.close_tab(tab)

    @pyqtSlot(webview.WebView)
    def on_window_close_requested(self, widget):
        """Close a tab with a widget given."""
        self.close_tab(widget)

    @pyqtSlot('QUrl', bool)
    def tabopen(self, url=None, background=None, explicit=False):
        """Open a new tab with a given URL.

        Inner logic for open-tab and open-tab-bg.
        Also connect all the signals we need to _filter_signals.

        Args:
            url: The URL to open as QUrl or None for an empty tab.
            background: Whether to open the tab in the background.
                        if None, the background-tabs setting decides.
            explicit: Whether the tab was opened explicitly.
                      If this is set, the new position might be different. With
                      the default settings we handle it like Chromium does:
                          - Tabs from clicked links etc. are to the right of
                            the current.
                          - Explicitly opened tabs are at the very right.

        Return:
            The opened WebView instance.
        """
        if url is not None:
            qtutils.ensure_valid(url)
        log.webview.debug("Creating new tab with URL {}".format(url))
        if config.get('tabs', 'tabs-are-windows') and self.count() > 0:
            from qutebrowser.mainwindow import mainwindow
            window = mainwindow.MainWindow()
            window.show()
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=window.win_id)
            return tabbed_browser.tabopen(url, background, explicit)
        tab = webview.WebView(self._win_id, self)
        self._connect_tab_signals(tab)
        idx = self._get_new_tab_idx(explicit)
        self.insertTab(idx, tab, "")
        if url is not None:
            tab.openurl(url)
        if background is None:
            background = config.get('tabs', 'background-tabs')
        if not background:
            self.setCurrentWidget(tab)
        tab.show()
        return tab

    def _get_new_tab_idx(self, explicit):
        """Get the index of a tab to insert.

        Args:
            explicit: Whether the tab was opened explicitly.

        Return:
            The index of the new tab.
        """
        if explicit:
            pos = config.get('tabs', 'new-tab-position-explicit')
        else:
            pos = config.get('tabs', 'new-tab-position')
        if pos == 'left':
            idx = self._tab_insert_idx_left
            # On first sight, we'd think we have to decrement
            # self._tab_insert_idx_left here, as we want the next tab to be
            # *before* the one we just opened. However, since we opened a tab
            # *to the left* of the currently focused tab, indices will shift by
            # 1 automatically.
        elif pos == 'right':
            idx = self._tab_insert_idx_right
            self._tab_insert_idx_right += 1
        elif pos == 'first':
            idx = 0
        elif pos == 'last':
            idx = -1
        else:
            raise ValueError("Invalid new-tab-position '{}'.".format(pos))
        log.webview.debug("new-tab-position {} -> opening new tab at {}, "
                          "next left: {} / right: {}".format(
                              pos, idx, self._tab_insert_idx_left,
                              self._tab_insert_idx_right))
        return idx

    @config.change_filter('tabs', 'show-favicons')
    def update_favicons(self):
        """Update favicons when config was changed."""
        show = config.get('tabs', 'show-favicons')
        for i, tab in enumerate(self.widgets()):
            if show:
                self.setTabIcon(i, tab.icon())
            else:
                self.setTabIcon(i, QIcon())

    @pyqtSlot()
    def on_load_started(self, tab):
        """Clear icon and update title when a tab started loading.

        Args:
            tab: The tab where the signal belongs to.
        """
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        self.update_tab_title(idx)
        if tab.keep_icon:
            tab.keep_icon = False
        else:
            self.setTabIcon(idx, QIcon())
        if idx == self.currentIndex():
            self.update_window_title()

    @pyqtSlot()
    def on_cur_load_started(self):
        """Leave insert/hint mode when loading started."""
        modeman.maybe_leave(self._win_id, usertypes.KeyMode.insert,
                            'load started')
        modeman.maybe_leave(self._win_id, usertypes.KeyMode.hint,
                            'load started')

    @pyqtSlot(webview.WebView, str)
    def on_title_changed(self, tab, text):
        """Set the title of a tab.

        Slot for the titleChanged signal of any tab.

        Args:
            tab: The WebView where the title was changed.
            text: The text to set.
        """
        if not text:
            log.webview.debug("Ignoring title change to '{}'.".format(text))
            return
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        log.webview.debug("Changing title for idx {} to '{}'".format(
            idx, text))
        self.set_page_title(idx, text)
        if idx == self.currentIndex():
            self.update_window_title()

    @pyqtSlot(webview.WebView, str)
    def on_url_text_changed(self, tab, url):
        """Set the new URL as title if there's no title yet.

        Args:
            tab: The WebView where the title was changed.
            url: The new URL.
        """
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        if not self.page_title(idx):
            self.set_page_title(idx, url)

    @pyqtSlot(webview.WebView)
    def on_icon_changed(self, tab):
        """Set the icon of a tab.

        Slot for the iconChanged signal of any tab.

        Args:
            tab: The WebView where the title was changed.
        """
        if not config.get('tabs', 'show-favicons'):
            return
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        self.setTabIcon(idx, tab.icon())

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode):
        """Give focus to current tab if command mode was left."""
        if mode in (usertypes.KeyMode.command, usertypes.KeyMode.prompt,
                    usertypes.KeyMode.yesno):
            widget = self.currentWidget()
            log.modes.debug("Left status-input mode, focusing {!r}".format(
                widget))
            if widget is None:
                return
            widget.setFocus()

    @pyqtSlot(int)
    def on_current_changed(self, idx):
        """Set last-focused-tab and leave hinting mode when focus changed."""
        if idx == -1 or self._shutting_down:
            # closing the last tab (before quitting) or shutting down
            return
        tab = self.widget(idx)
        log.modes.debug("Current tab changed, focusing {!r}".format(tab))
        tab.setFocus()
        for mode in (usertypes.KeyMode.hint, usertypes.KeyMode.insert,
                     usertypes.KeyMode.caret):
            modeman.maybe_leave(self._win_id, mode, 'tab changed')
        if self._now_focused is not None:
            objreg.register('last-focused-tab', self._now_focused, update=True,
                            scope='window', window=self._win_id)
        self._now_focused = tab
        self.current_tab_changed.emit(tab)
        QTimer.singleShot(0, self.update_window_title)
        self._tab_insert_idx_left = self.currentIndex()
        self._tab_insert_idx_right = self.currentIndex() + 1

    @pyqtSlot()
    def on_cmd_return_pressed(self):
        """Set focus when the commandline closes."""
        log.modes.debug("Commandline closed, focusing {!r}".format(self))

    def on_load_progress(self, tab, perc):
        """Adjust tab indicator on load progress."""
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        start = config.get('colors', 'tabs.indicator.start')
        stop = config.get('colors', 'tabs.indicator.stop')
        system = config.get('colors', 'tabs.indicator.system')
        color = utils.interpolate_color(start, stop, perc, system)
        self.set_tab_indicator_color(idx, color)
        self.update_tab_title(idx)
        if idx == self.currentIndex():
            self.update_window_title()

    def on_load_finished(self, tab):
        """Adjust tab indicator when loading finished.

        We don't take loadFinished's ok argument here as it always seems to be
        true when the QWebPage has an ErrorPageExtension implemented.
        See https://github.com/The-Compiler/qutebrowser/issues/84
        """
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        if tab.page().error_occurred:
            color = config.get('colors', 'tabs.indicator.error')
        else:
            start = config.get('colors', 'tabs.indicator.start')
            stop = config.get('colors', 'tabs.indicator.stop')
            system = config.get('colors', 'tabs.indicator.system')
            color = utils.interpolate_color(start, stop, 100, system)
        self.set_tab_indicator_color(idx, color)
        self.update_tab_title(idx)
        if idx == self.currentIndex():
            self.update_window_title()

    def resizeEvent(self, e):
        """Extend resizeEvent of QWidget to emit a resized signal afterwards.

        Args:
            e: The QResizeEvent
        """
        super().resizeEvent(e)
        self.resized.emit(self.geometry())

    def wheelEvent(self, e):
        """Override wheelEvent of QWidget to forward it to the focused tab.

        Args:
            e: The QWheelEvent
        """
        if self._now_focused is not None:
            self._now_focused.wheelEvent(e)
        else:
            e.ignore()
