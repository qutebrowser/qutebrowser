# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
from qutebrowser.browser import signalfilter, browsertab
from qutebrowser.utils import (log, usertypes, utils, qtutils, objreg,
                               urlutils, message)


UndoEntry = collections.namedtuple('UndoEntry', ['url', 'history', 'index'])


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
        search_text/search_options: Search parameters which are shared between
                                    all tabs.
        _win_id: The window ID this tabbedbrowser is associated with.
        _filter: A SignalFilter instance.
        _now_focused: The tab which is focused now.
        _tab_insert_idx_left: Where to insert a new tab with
                         tabbar -> new-tab-position set to 'prev'.
        _tab_insert_idx_right: Same as above, for 'next'.
        _undo_stack: List of UndoEntry namedtuples of closed tabs.
        shutting_down: Whether we're currently shutting down.
        _local_marks: Jump markers local to each page
        _global_marks: Jump markers used across all pages
        default_window_icon: The qutebrowser window icon

    Signals:
        cur_progress: Progress of the current tab changed (load_progress).
        cur_load_started: Current tab started loading (load_started)
        cur_load_finished: Current tab finished loading (load_finished)
        cur_url_changed: Current URL changed.
        cur_link_hovered: Link hovered in current tab (link_hovered)
        cur_scroll_perc_changed: Scroll percentage of current tab changed.
                                 arg 1: x-position in %.
                                 arg 2: y-position in %.
        cur_load_status_changed: Loading status of current tab changed.
        close_window: The last tab was closed, close this window.
        resized: Emitted when the browser window has resized, so the completion
                 widget can adjust its size to it.
                 arg: The new size.
        current_tab_changed: The current tab changed to the emitted tab.
        new_tab: Emits the new WebView and its index when a new tab is opened.
    """

    cur_progress = pyqtSignal(int)
    cur_load_started = pyqtSignal()
    cur_load_finished = pyqtSignal(bool)
    cur_url_changed = pyqtSignal(QUrl)
    cur_link_hovered = pyqtSignal(str)
    cur_scroll_perc_changed = pyqtSignal(int, int)
    cur_load_status_changed = pyqtSignal(str)
    close_window = pyqtSignal()
    resized = pyqtSignal('QRect')
    current_tab_changed = pyqtSignal(browsertab.AbstractTab)
    new_tab = pyqtSignal(browsertab.AbstractTab, int)

    def __init__(self, win_id, parent=None):
        super().__init__(win_id, parent)
        self._win_id = win_id
        self._tab_insert_idx_left = 0
        self._tab_insert_idx_right = -1
        self.shutting_down = False
        self.tabCloseRequested.connect(self.on_tab_close_requested)
        self.currentChanged.connect(self.on_current_changed)
        self.cur_load_started.connect(self.on_cur_load_started)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._undo_stack = []
        self._filter = signalfilter.SignalFilter(win_id, self)
        self._now_focused = None
        self.search_text = None
        self.search_options = {}
        self._local_marks = {}
        self._global_marks = {}
        self.default_window_icon = self.window().windowIcon()
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
        fields = self.get_tab_fields(idx)
        fields['id'] = self._win_id

        fmt = config.get('ui', 'window-title-format')
        self.window().setWindowTitle(fmt.format(**fields))

    def _connect_tab_signals(self, tab):
        """Set up the needed signals for tab."""
        # filtered signals
        tab.link_hovered.connect(
            self._filter.create(self.cur_link_hovered, tab))
        tab.load_progress.connect(
            self._filter.create(self.cur_progress, tab))
        tab.load_finished.connect(
            self._filter.create(self.cur_load_finished, tab))
        tab.load_started.connect(
            self._filter.create(self.cur_load_started, tab))
        tab.scroller.perc_changed.connect(
            self._filter.create(self.cur_scroll_perc_changed, tab))
        tab.scroller.perc_changed.connect(self.on_scroll_pos_changed)
        tab.url_changed.connect(
            self._filter.create(self.cur_url_changed, tab))
        tab.load_status_changed.connect(
            self._filter.create(self.cur_load_status_changed, tab))
        tab.url_changed.connect(
            functools.partial(self.on_url_changed, tab))
        # misc
        tab.title_changed.connect(
            functools.partial(self.on_title_changed, tab))
        tab.icon_changed.connect(
            functools.partial(self.on_icon_changed, tab))
        tab.load_progress.connect(
            functools.partial(self.on_load_progress, tab))
        tab.load_finished.connect(
            functools.partial(self.on_load_finished, tab))
        tab.load_started.connect(
            functools.partial(self.on_load_started, tab))
        tab.window_close_requested.connect(
            functools.partial(self.on_window_close_requested, tab))
        tab.new_tab_requested.connect(self.tabopen)
        tab.add_history_item.connect(objreg.get('web-history').add_from_tab)

    def current_url(self):
        """Get the URL of the current tab.

        Intended to be used from command handlers.

        Return:
            The current URL as QUrl.
        """
        idx = self.currentIndex()
        return super().tab_url(idx)

    def shutdown(self):
        """Try to shut down all tabs cleanly."""
        self.shutting_down = True
        for tab in self.widgets():
            self._remove_tab(tab)

    def close_tab(self, tab, *, add_undo=True):
        """Close a tab.

        Args:
            tab: The QWebView to be closed.
            add_undo: Whether the tab close can be undone.
        """
        last_close = config.get('tabs', 'last-close')
        count = self.count()

        if last_close == 'ignore' and count == 1:
            return

        self._remove_tab(tab, add_undo=add_undo)

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

    def _remove_tab(self, tab, *, add_undo=True):
        """Remove a tab from the tab list and delete it properly.

        Args:
            tab: The QWebView to be closed.
            add_undo: Whether the tab close can be undone.
        """
        idx = self.indexOf(tab)
        if idx == -1:
            raise TabDeletedError("tab {} is not contained in "
                                  "TabbedWidget!".format(tab))
        if tab is self._now_focused:
            self._now_focused = None
        if tab is objreg.get('last-focused-tab', None, scope='window',
                             window=self._win_id):
            objreg.delete('last-focused-tab', scope='window',
                          window=self._win_id)
        if tab.url().isValid():
            history_data = tab.history.serialize()
            if add_undo:
                entry = UndoEntry(tab.url(), history_data, idx)
                self._undo_stack.append(entry)
        elif tab.url().isEmpty():
            # There are some good reasons why a URL could be empty
            # (target="_blank" with a download, see [1]), so we silently ignore
            # this.
            # [1] https://github.com/The-Compiler/qutebrowser/issues/163
            pass
        else:
            # We display a warnings for URLs which are not empty but invalid -
            # but we don't return here because we want the tab to close either
            # way.
            urlutils.invalid_url_error(tab.url(), "saving tab")
        tab.shutdown()
        self.removeTab(idx)
        tab.deleteLater()

    def undo(self):
        """Undo removing of a tab."""
        # Remove unused tab which may be created after the last tab is closed
        last_close = config.get('tabs', 'last-close')
        use_current_tab = False
        if last_close in ['blank', 'startpage', 'default-page']:
            only_one_tab_open = self.count() == 1
            no_history = len(self.widget(0).history) == 1
            urls = {
                'blank': QUrl('about:blank'),
                'startpage': QUrl(config.get('general', 'startpage')[0]),
                'default-page': config.get('general', 'default-page'),
            }
            first_tab_url = self.widget(0).url()
            last_close_urlstr = urls[last_close].toString().rstrip('/')
            first_tab_urlstr = first_tab_url.toString().rstrip('/')
            last_close_url_used = first_tab_urlstr == last_close_urlstr
            use_current_tab = (only_one_tab_open and no_history and
                               last_close_url_used)

        url, history_data, idx = self._undo_stack.pop()

        if use_current_tab:
            self.openurl(url, newtab=False)
            newtab = self.widget(0)
        else:
            newtab = self.tabopen(url, background=False, idx=idx)

        newtab.history.deserialize(history_data)

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

    @pyqtSlot(browsertab.AbstractTab)
    def on_window_close_requested(self, widget):
        """Close a tab with a widget given."""
        try:
            self.close_tab(widget)
        except TabDeletedError:
            log.webview.debug("Requested to close {!r} which does not "
                              "exist!".format(widget))

    @pyqtSlot('QUrl')
    @pyqtSlot('QUrl', bool)
    def tabopen(self, url=None, background=None, explicit=False, idx=None, *,
                ignore_tabs_are_windows=False):
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
            idx: The index where the new tab should be opened.
            ignore_tabs_are_windows: If given, never open a new window, even
                                     with tabs-are-windows set.

        Return:
            The opened WebView instance.
        """
        if url is not None:
            qtutils.ensure_valid(url)
        log.webview.debug("Creating new tab with URL {}, background {}, "
                          "explicit {}, idx {}".format(
                              url, background, explicit, idx))

        if (config.get('tabs', 'tabs-are-windows') and self.count() > 0 and
                not ignore_tabs_are_windows):
            from qutebrowser.mainwindow import mainwindow
            window = mainwindow.MainWindow()
            window.show()
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=window.win_id)
            return tabbed_browser.tabopen(url, background, explicit)

        tab = browsertab.create(win_id=self._win_id, parent=self)
        self._connect_tab_signals(tab)

        if idx is None:
            idx = self._get_new_tab_idx(explicit)
        self.insertTab(idx, tab, "")

        if url is not None:
            tab.openurl(url)
        if background is None:
            background = config.get('tabs', 'background-tabs')
        if background:
            self.tab_index_changed.emit(self.currentIndex(), self.count())
        else:
            self.setCurrentWidget(tab)
        tab.show()
        self.new_tab.emit(tab, idx)
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
        if pos == 'prev':
            idx = self._tab_insert_idx_left
            # On first sight, we'd think we have to decrement
            # self._tab_insert_idx_left here, as we want the next tab to be
            # *before* the one we just opened. However, since we opened a tab
            # *before* the currently focused tab, indices will shift by
            # 1 automatically.
        elif pos == 'next':
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
        tabs_are_wins = config.get('tabs', 'tabs-are-windows')
        for i, tab in enumerate(self.widgets()):
            if show:
                self.setTabIcon(i, tab.icon())
                if tabs_are_wins:
                    self.window().setWindowIcon(tab.icon())
            else:
                self.setTabIcon(i, QIcon())
                if tabs_are_wins:
                    self.window().setWindowIcon(self.default_window_icon)

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
        if tab.data.keep_icon:
            tab.data.keep_icon = False
        else:
            self.setTabIcon(idx, QIcon())
            if (config.get('tabs', 'tabs-are-windows') and
                    config.get('tabs', 'show-favicons')):
                self.window().setWindowIcon(self.default_window_icon)
        if idx == self.currentIndex():
            self.update_window_title()

    @pyqtSlot()
    def on_cur_load_started(self):
        """Leave insert/hint mode when loading started."""
        modeman.leave(self._win_id, usertypes.KeyMode.insert, 'load started',
                      maybe=True)
        modeman.leave(self._win_id, usertypes.KeyMode.hint, 'load started',
                      maybe=True)

    @pyqtSlot(browsertab.AbstractTab, str)
    def on_title_changed(self, tab, text):
        """Set the title of a tab.

        Slot for the title_changed signal of any tab.

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

    @pyqtSlot(browsertab.AbstractTab, QUrl)
    def on_url_changed(self, tab, url):
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

        # If needed, re-open the tab as a workaround for QTBUG-54419.
        # See https://bugreports.qt.io/browse/QTBUG-54419
        if (tab.backend == usertypes.Backend.QtWebEngine and
                tab.needs_qtbug54419_workaround and url.isValid()):
            log.misc.debug("Doing QTBUG-54419 workaround for {}, "
                           "url {}".format(tab, url))
            background = self.currentIndex() != idx
            self.setUpdatesEnabled(False)
            try:
                self.tabopen(url, background=background, idx=idx,
                             ignore_tabs_are_windows=True)
                self.close_tab(tab, add_undo=False)
            finally:
                self.setUpdatesEnabled(True)
            tab.needs_qtbug54419_workaround = False

    @pyqtSlot(browsertab.AbstractTab, QIcon)
    def on_icon_changed(self, tab, icon):
        """Set the icon of a tab.

        Slot for the iconChanged signal of any tab.

        Args:
            tab: The WebView where the title was changed.
            icon: The new icon
        """
        if not config.get('tabs', 'show-favicons'):
            return
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        self.setTabIcon(idx, icon)
        if config.get('tabs', 'tabs-are-windows'):
            self.window().setWindowIcon(icon)

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode):
        """Give focus to current tab if command mode was left."""
        if mode in [usertypes.KeyMode.command, usertypes.KeyMode.prompt,
                    usertypes.KeyMode.yesno]:
            widget = self.currentWidget()
            log.modes.debug("Left status-input mode, focusing {!r}".format(
                widget))
            if widget is None:
                return
            widget.setFocus()

    @pyqtSlot(int)
    def on_current_changed(self, idx):
        """Set last-focused-tab and leave hinting mode when focus changed."""
        if idx == -1 or self.shutting_down:
            # closing the last tab (before quitting) or shutting down
            return
        tab = self.widget(idx)
        if tab is None:
            log.webview.debug("on_current_changed got called with invalid "
                              "index {}".format(idx))
            return

        log.modes.debug("Current tab changed, focusing {!r}".format(tab))
        tab.setFocus()
        for mode in [usertypes.KeyMode.hint, usertypes.KeyMode.insert,
                     usertypes.KeyMode.caret, usertypes.KeyMode.passthrough]:
            modeman.leave(self._win_id, mode, 'tab changed', maybe=True)
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

    def on_load_finished(self, tab, ok):
        """Adjust tab indicator when loading finished."""
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        if ok:
            start = config.get('colors', 'tabs.indicator.start')
            stop = config.get('colors', 'tabs.indicator.stop')
            system = config.get('colors', 'tabs.indicator.system')
            color = utils.interpolate_color(start, stop, 100, system)
        else:
            color = config.get('colors', 'tabs.indicator.error')
        self.set_tab_indicator_color(idx, color)
        self.update_tab_title(idx)
        if idx == self.currentIndex():
            self.update_window_title()

    @pyqtSlot()
    def on_scroll_pos_changed(self):
        """Update tab and window title when scroll position changed."""
        idx = self.currentIndex()
        if idx == -1:
            # (e.g. last tab removed)
            log.webview.debug("Not updating scroll position because index is "
                              "-1")
            return
        self.update_window_title()
        self.update_tab_title(idx)

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

    def set_mark(self, key):
        """Set a mark at the current scroll position in the current tab.

        Args:
            key: mark identifier; capital indicates a global mark
        """
        # strip the fragment as it may interfere with scrolling
        try:
            url = self.current_url().adjusted(QUrl.RemoveFragment)
        except qtutils.QtValueError:
            # show an error only if the mark is not automatically set
            if key != "'":
                message.error("Failed to set mark: url invalid")
            return
        point = self.currentWidget().scroller.pos_px()

        if key.isupper():
            self._global_marks[key] = point, url
        else:
            if url not in self._local_marks:
                self._local_marks[url] = {}
            self._local_marks[url][key] = point

    def jump_mark(self, key):
        """Jump to the mark named by `key`.

        Args:
            key: mark identifier; capital indicates a global mark
        """
        try:
            # consider urls that differ only in fragment to be identical
            urlkey = self.current_url().adjusted(QUrl.RemoveFragment)
        except qtutils.QtValueError:
            urlkey = None

        tab = self.currentWidget()

        if key.isupper():
            if key in self._global_marks:
                point, url = self._global_marks[key]

                def callback(ok):
                    if ok:
                        self.cur_load_finished.disconnect(callback)
                        tab.scroller.to_point(point)

                self.openurl(url, newtab=False)
                self.cur_load_finished.connect(callback)
            else:
                message.error("Mark {} is not set".format(key))
        elif urlkey is None:
            message.error("Current URL is invalid!")
        elif urlkey in self._local_marks and key in self._local_marks[urlkey]:
            point = self._local_marks[urlkey][key]

            # save the pre-jump position in the special ' mark
            # this has to happen after we read the mark, otherwise jump_mark
            # "'" would just jump to the current position every time
            self.set_mark("'")

            tab.scroller.to_point(point)
        else:
            message.error("Mark {} is not set".format(key))
