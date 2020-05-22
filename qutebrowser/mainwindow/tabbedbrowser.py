# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import collections
import functools
import weakref
import typing

import attr
from PyQt5.QtWidgets import QSizePolicy, QWidget, QApplication
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QTimer, QUrl
from PyQt5.QtGui import QIcon

from qutebrowser.config import config
from qutebrowser.keyinput import modeman
from qutebrowser.mainwindow import tabwidget, mainwindow
from qutebrowser.browser import signalfilter, browsertab, history
from qutebrowser.utils import (log, usertypes, utils, qtutils, objreg,
                               urlutils, message, jinja)
from qutebrowser.misc import quitter


@attr.s
class UndoEntry:

    """Information needed for :undo."""

    url = attr.ib()
    history = attr.ib()
    index = attr.ib()
    pinned = attr.ib()


class TabDeque:

    """Class which manages the 'last visited' tab stack.

    Instead of handling deletions by clearing old entries, they are handled by
    checking if they exist on access. This allows us to save an iteration on
    every tab delete.

    Currently, we assume we will switch to the tab returned by any of the
    getter functions. This is done because the on_switch functions will be
    called upon switch, and we don't want to duplicate entries in the stack
    for a single switch.
    """

    def __init__(self) -> None:
        self._stack = collections.deque(
            maxlen=config.val.tabs.focus_stack_size
        )  # type: typing.Deque[weakref.ReferenceType[QWidget]]
        # Items that have been removed from the primary stack.
        self._stack_deleted = [
        ]  # type: typing.List[weakref.ReferenceType[QWidget]]
        self._ignore_next = False
        self._keep_deleted_next = False

    def on_switch(self, old_tab: QWidget) -> None:
        """Record tab switch events."""
        if self._ignore_next:
            self._ignore_next = False
            self._keep_deleted_next = False
            return
        tab = weakref.ref(old_tab)
        if self._stack_deleted and not self._keep_deleted_next:
            self._stack_deleted = []
        self._keep_deleted_next = False
        self._stack.append(tab)

    def prev(self, cur_tab: QWidget) -> QWidget:
        """Get the 'previous' tab in the stack.

        Throws IndexError on failure.
        """
        tab = None  # type: typing.Optional[QWidget]
        while tab is None or tab.pending_removal or tab is cur_tab:
            tab = self._stack.pop()()
        self._stack_deleted.append(weakref.ref(cur_tab))
        self._ignore_next = True
        return tab

    def next(self, cur_tab: QWidget, *, keep_overflow: bool = True) -> QWidget:
        """Get the 'next' tab in the stack.

        Throws IndexError on failure.
        """
        tab = None  # type: typing.Optional[QWidget]
        while tab is None or tab.pending_removal or tab is cur_tab:
            tab = self._stack_deleted.pop()()
        # On next tab-switch, current tab will be added to stack as normal.
        # However, we shouldn't wipe the overflow stack as normal.
        if keep_overflow:
            self._keep_deleted_next = True
        return tab

    def last(self, cur_tab: QWidget) -> QWidget:
        """Get the last tab.

        Throws IndexError on failure.
        """
        try:
            return self.next(cur_tab, keep_overflow=False)
        except IndexError:
            return self.prev(cur_tab)

    def update_size(self) -> None:
        """Update the maxsize of this TabDeque."""
        newsize = config.val.tabs.focus_stack_size
        if newsize < 0:
            newsize = None
        # We can't resize a collections.deque so just recreate it >:(
        self._stack = collections.deque(self._stack, maxlen=newsize)


class TabDeletedError(Exception):

    """Exception raised when _tab_index is called for a deleted tab."""


class TabbedBrowser(QWidget):

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
                              tabs.new_tab_position set to 'prev'.
        _tab_insert_idx_right: Same as above, for 'next'.
        _undo_stack: List of lists of UndoEntry objects of closed tabs.
        shutting_down: Whether we're currently shutting down.
        _local_marks: Jump markers local to each page
        _global_marks: Jump markers used across all pages
        default_window_icon: The qutebrowser window icon
        is_private: Whether private browsing is on for this window.

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
    cur_load_status_changed = pyqtSignal(usertypes.LoadStatus)
    cur_fullscreen_requested = pyqtSignal(bool)
    cur_caret_selection_toggled = pyqtSignal(browsertab.SelectionState)
    close_window = pyqtSignal()
    resized = pyqtSignal('QRect')
    current_tab_changed = pyqtSignal(browsertab.AbstractTab)
    new_tab = pyqtSignal(browsertab.AbstractTab, int)

    def __init__(self, *, win_id, private, parent=None):
        if private:
            assert not qtutils.is_single_process()
        super().__init__(parent)
        self.widget = tabwidget.TabWidget(win_id, parent=self)
        self._win_id = win_id
        self._tab_insert_idx_left = 0
        self._tab_insert_idx_right = -1
        self.shutting_down = False
        self.widget.tabCloseRequested.connect(self.on_tab_close_requested)
        self.widget.new_tab_requested.connect(
            self.tabopen)  # type: ignore[arg-type]
        self.widget.currentChanged.connect(self._on_current_changed)
        self.cur_fullscreen_requested.connect(self.widget.tabBar().maybe_hide)
        self.widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-65223
        if qtutils.version_check('5.10', compiled=False):
            self.cur_load_finished.connect(self._leave_modes_on_load)
        else:
            self.cur_load_started.connect(self._leave_modes_on_load)

        # This init is never used, it is immediately thrown away in the next
        # line.
        self._undo_stack = (
            collections.deque()
        )  # type: typing.MutableSequence[typing.MutableSequence[UndoEntry]]
        self._update_stack_size()
        self._filter = signalfilter.SignalFilter(win_id, self)
        self._now_focused = None
        self.search_text = None
        self.search_options = {}  # type: typing.Mapping[str, typing.Any]
        self._local_marks = {
        }  # type: typing.MutableMapping[QUrl, typing.MutableMapping[str, int]]
        self._global_marks = {
        }  # type: typing.MutableMapping[str, typing.Tuple[int, QUrl]]
        self.default_window_icon = self.widget.window().windowIcon()
        self.is_private = private
        self.tab_deque = TabDeque()
        config.instance.changed.connect(self._on_config_changed)
        quitter.instance.shutting_down.connect(self.shutdown)

    def _update_stack_size(self):
        newsize = config.instance.get('tabs.undo_stack_size')
        if newsize < 0:
            newsize = None
        # We can't resize a collections.deque so just recreate it >:(
        self._undo_stack = collections.deque(self._undo_stack, maxlen=newsize)

    def __repr__(self):
        return utils.get_repr(self, count=self.widget.count())

    @pyqtSlot(str)
    def _on_config_changed(self, option):
        if option == 'tabs.favicons.show':
            self._update_favicons()
        elif option == 'window.title_format':
            self._update_window_title()
        elif option == 'tabs.undo_stack_size':
            self._update_stack_size()
        elif option in ['tabs.title.format', 'tabs.title.format_pinned']:
            self.widget.update_tab_titles()
        elif option == "tabs.focus_stack_size":
            self.tab_deque.update_size()

    def _tab_index(self, tab):
        """Get the index of a given tab.

        Raises TabDeletedError if the tab doesn't exist anymore.
        """
        try:
            idx = self.widget.indexOf(tab)
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
        widgets = []
        for i in range(self.widget.count()):
            widget = self.widget.widget(i)
            if widget is None:
                log.webview.debug(  # type: ignore[unreachable]
                    "Got None-widget in tabbedbrowser!")
            else:
                widgets.append(widget)
        return widgets

    def _update_window_title(self, field=None):
        """Change the window title to match the current tab.

        Args:
            idx: The tab index to update.
            field: A field name which was updated. If given, the title
                   is only set if the given field is in the template.
        """
        title_format = config.cache['window.title_format']
        if field is not None and ('{' + field + '}') not in title_format:
            return

        idx = self.widget.currentIndex()
        if idx == -1:
            # (e.g. last tab removed)
            log.webview.debug("Not updating window title because index is -1")
            return
        fields = self.widget.get_tab_fields(idx)
        fields['id'] = self._win_id

        title = title_format.format(**fields)
        self.widget.window().setWindowTitle(title)

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
        tab.url_changed.connect(
            self._filter.create(self.cur_url_changed, tab))
        tab.load_status_changed.connect(
            self._filter.create(self.cur_load_status_changed, tab))
        tab.fullscreen_requested.connect(
            self._filter.create(self.cur_fullscreen_requested, tab))
        tab.caret.selection_toggled.connect(
            self._filter.create(self.cur_caret_selection_toggled, tab))
        # misc
        tab.scroller.perc_changed.connect(self._on_scroll_pos_changed)
        tab.scroller.before_jump_requested.connect(lambda: self.set_mark("'"))
        tab.url_changed.connect(
            functools.partial(self._on_url_changed, tab))
        tab.title_changed.connect(
            functools.partial(self._on_title_changed, tab))
        tab.icon_changed.connect(
            functools.partial(self._on_icon_changed, tab))
        tab.load_progress.connect(
            functools.partial(self._on_load_progress, tab))
        tab.load_finished.connect(
            functools.partial(self._on_load_finished, tab))
        tab.load_started.connect(
            functools.partial(self._on_load_started, tab))
        tab.load_status_changed.connect(
            functools.partial(self._on_load_status_changed, tab))
        tab.window_close_requested.connect(
            functools.partial(self._on_window_close_requested, tab))
        tab.renderer_process_terminated.connect(
            functools.partial(self._on_renderer_process_terminated, tab))
        tab.audio.muted_changed.connect(
            functools.partial(self._on_audio_changed, tab))
        tab.audio.recently_audible_changed.connect(
            functools.partial(self._on_audio_changed, tab))
        tab.new_tab_requested.connect(self.tabopen)
        if not self.is_private:
            tab.history_item_triggered.connect(
                history.web_history.add_from_tab)

    def current_url(self):
        """Get the URL of the current tab.

        Intended to be used from command handlers.

        Return:
            The current URL as QUrl.
        """
        idx = self.widget.currentIndex()
        return self.widget.tab_url(idx)

    def shutdown(self):
        """Try to shut down all tabs cleanly."""
        self.shutting_down = True
        # Reverse tabs so we don't have to recacluate tab titles over and over
        # Removing first causes [2..-1] to be recomputed
        # Removing the last causes nothing to be recomputed
        for tab in reversed(self.widgets()):
            self._remove_tab(tab)

    def tab_close_prompt_if_pinned(
            self, tab, force, yes_action,
            text="Are you sure you want to close a pinned tab?"):
        """Helper method for tab_close.

        If tab is pinned, prompt. If not, run yes_action.
        If tab is destroyed, abort question.
        """
        if tab.data.pinned and not force:
            message.confirm_async(
                title='Pinned Tab',
                text=text,
                yes_action=yes_action, default=False, abort_on=[tab.destroyed])
        else:
            yes_action()

    def close_tab(self, tab, *, add_undo=True, new_undo=True):
        """Close a tab.

        Args:
            tab: The QWebView to be closed.
            add_undo: Whether the tab close can be undone.
            new_undo: Whether the undo entry should be a new item in the stack.
        """
        last_close = config.val.tabs.last_close
        count = self.widget.count()

        if last_close == 'ignore' and count == 1:
            return

        self._remove_tab(tab, add_undo=add_undo, new_undo=new_undo)

        if count == 1:  # We just closed the last tab above.
            if last_close == 'close':
                self.close_window.emit()
            elif last_close == 'blank':
                self.load_url(QUrl('about:blank'), newtab=True)
            elif last_close == 'startpage':
                for url in config.val.url.start_pages:
                    self.load_url(url, newtab=True)
            elif last_close == 'default-page':
                self.load_url(config.val.url.default_page, newtab=True)

    def _remove_tab(self, tab, *, add_undo=True, new_undo=True, crashed=False):
        """Remove a tab from the tab list and delete it properly.

        Args:
            tab: The QWebView to be closed.
            add_undo: Whether the tab close can be undone.
            new_undo: Whether the undo entry should be a new item in the stack.
            crashed: Whether we're closing a tab with crashed renderer process.
        """
        idx = self.widget.indexOf(tab)
        if idx == -1:
            if crashed:
                return
            raise TabDeletedError("tab {} is not contained in "
                                  "TabbedWidget!".format(tab))
        if tab is self._now_focused:
            self._now_focused = None

        tab.pending_removal = True

        if tab.url().isEmpty():
            # There are some good reasons why a URL could be empty
            # (target="_blank" with a download, see [1]), so we silently ignore
            # this.
            # [1] https://github.com/qutebrowser/qutebrowser/issues/163
            pass
        elif not tab.url().isValid():
            # We display a warning for URLs which are not empty but invalid -
            # but we don't return here because we want the tab to close either
            # way.
            urlutils.invalid_url_error(tab.url(), "saving tab")
        elif add_undo:
            try:
                history_data = tab.history.private_api.serialize()
            except browsertab.WebTabError:
                pass  # special URL
            else:
                entry = UndoEntry(tab.url(), history_data, idx,
                                  tab.data.pinned)
                if new_undo or not self._undo_stack:
                    self._undo_stack.append([entry])
                else:
                    self._undo_stack[-1].append(entry)

        tab.private_api.shutdown()
        self.widget.removeTab(idx)
        if not crashed:
            # WORKAROUND for a segfault when we delete the crashed tab.
            # see https://bugreports.qt.io/browse/QTBUG-58698
            tab.layout().unwrap()
            tab.deleteLater()

    def undo(self):
        """Undo removing of a tab or tabs."""
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

            newtab.history.private_api.deserialize(entry.history)
            self.widget.set_tab_pinned(newtab, entry.pinned)

    @pyqtSlot('QUrl', bool)
    def load_url(self, url, newtab):
        """Open a URL, used as a slot.

        Args:
            url: The URL to open as QUrl.
            newtab: True to open URL in a new tab, False otherwise.
        """
        qtutils.ensure_valid(url)
        if newtab or self.widget.currentWidget() is None:
            self.tabopen(url, background=False)
        else:
            self.widget.currentWidget().load_url(url)

    @pyqtSlot(int)
    def on_tab_close_requested(self, idx):
        """Close a tab via an index."""
        tab = self.widget.widget(idx)
        if tab is None:
            log.webview.debug(  # type: ignore[unreachable]
                "Got invalid tab {} for index {}!".format(tab, idx))
            return
        self.tab_close_prompt_if_pinned(
            tab, False, lambda: self.close_tab(tab))

    @pyqtSlot(browsertab.AbstractTab)
    def _on_window_close_requested(self, widget):
        """Close a tab with a widget given."""
        try:
            self.close_tab(widget)
        except TabDeletedError:
            log.webview.debug("Requested to close {!r} which does not "
                              "exist!".format(widget))

    @pyqtSlot('QUrl')
    @pyqtSlot('QUrl', bool)
    @pyqtSlot('QUrl', bool, bool)
    def tabopen(
            self, url: QUrl = None,
            background: bool = None,
            related: bool = True,
            idx: int = None,
    ) -> browsertab.AbstractTab:
        """Open a new tab with a given URL.

        Inner logic for open-tab and open-tab-bg.
        Also connect all the signals we need to _filter_signals.

        Args:
            url: The URL to open as QUrl or None for an empty tab.
            background: Whether to open the tab in the background.
                        if None, the `tabs.background` setting decides.
            related: Whether the tab was opened from another existing tab.
                     If this is set, the new position might be different. With
                     the default settings we handle it like Chromium does:
                         - Tabs from clicked links etc. are to the right of
                           the current (related=True).
                         - Explicitly opened tabs are at the very right
                           (related=False)
            idx: The index where the new tab should be opened.

        Return:
            The opened WebView instance.
        """
        if url is not None:
            qtutils.ensure_valid(url)
        log.webview.debug("Creating new tab with URL {}, background {}, "
                          "related {}, idx {}".format(
                              url, background, related, idx))

        prev_focus = QApplication.focusWidget()

        if config.val.tabs.tabs_are_windows and self.widget.count() > 0:
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
            idx = self._get_new_tab_idx(related)
        self.widget.insertTab(idx, tab, "")

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

    def _get_new_tab_idx(self, related):
        """Get the index of a tab to insert.

        Args:
            related: Whether the tab was opened from another tab (as a "child")

        Return:
            The index of the new tab.
        """
        if related:
            pos = config.val.tabs.new_position.related
        else:
            pos = config.val.tabs.new_position.unrelated
        if pos == 'prev':
            if config.val.tabs.new_position.stacking:
                idx = self._tab_insert_idx_left
                # On first sight, we'd think we have to decrement
                # self._tab_insert_idx_left here, as we want the next tab to be
                # *before* the one we just opened. However, since we opened a
                # tab *before* the currently focused tab, indices will shift by
                # 1 automatically.
            else:
                idx = self.widget.currentIndex()
        elif pos == 'next':
            if config.val.tabs.new_position.stacking:
                idx = self._tab_insert_idx_right
            else:
                idx = self.widget.currentIndex() + 1
            self._tab_insert_idx_right += 1
        elif pos == 'first':
            idx = 0
        elif pos == 'last':
            idx = -1
        else:
            raise ValueError("Invalid tabs.new_position '{}'.".format(pos))
        log.webview.debug("tabs.new_position {} -> opening new tab at {}, "
                          "next left: {} / right: {}".format(
                              pos, idx, self._tab_insert_idx_left,
                              self._tab_insert_idx_right))
        return idx

    def _update_favicons(self):
        """Update favicons when config was changed."""
        for tab in self.widgets():
            self.widget.update_tab_favicon(tab)

    @pyqtSlot()
    def _on_load_started(self, tab):
        """Clear icon and update title when a tab started loading.

        Args:
            tab: The tab where the signal belongs to.
        """
        if tab.data.keep_icon:
            tab.data.keep_icon = False
        else:
            if (config.cache['tabs.tabs_are_windows'] and
                    tab.data.should_show_icon()):
                self.widget.window().setWindowIcon(self.default_window_icon)

    @pyqtSlot()
    def _on_load_status_changed(self, tab):
        """Update tab/window titles if the load status changed."""
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return

        self.widget.update_tab_title(idx)
        if idx == self.widget.currentIndex():
            self._update_window_title()

    @pyqtSlot()
    def _leave_modes_on_load(self):
        """Leave insert/hint mode when loading started."""
        try:
            url = self.current_url()
            if not url.isValid():
                url = None
        except qtutils.QtValueError:
            url = None
        if config.instance.get('input.insert_mode.leave_on_load',
                               url=url):
            modeman.leave(self._win_id, usertypes.KeyMode.insert,
                          'load started', maybe=True)
        else:
            log.modes.debug("Ignoring leave_on_load request due to setting.")
        if config.cache['hints.leave_on_load']:
            modeman.leave(self._win_id, usertypes.KeyMode.hint,
                          'load started', maybe=True)
        else:
            log.modes.debug("Ignoring leave_on_load request due to setting.")

    @pyqtSlot(browsertab.AbstractTab, str)
    def _on_title_changed(self, tab, text):
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
        self.widget.set_page_title(idx, text)
        if idx == self.widget.currentIndex():
            self._update_window_title()

    @pyqtSlot(browsertab.AbstractTab, QUrl)
    def _on_url_changed(self, tab, url):
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

        if not self.widget.page_title(idx):
            self.widget.set_page_title(idx, url.toDisplayString())

    @pyqtSlot(browsertab.AbstractTab, QIcon)
    def _on_icon_changed(self, tab, icon):
        """Set the icon of a tab.

        Slot for the iconChanged signal of any tab.

        Args:
            tab: The WebView where the title was changed.
            icon: The new icon
        """
        if not tab.data.should_show_icon():
            return
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        self.widget.setTabIcon(idx, icon)
        if config.val.tabs.tabs_are_windows:
            self.widget.window().setWindowIcon(icon)

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_entered(self, mode):
        """Save input mode when tabs.mode_on_change = restore."""
        if (config.val.tabs.mode_on_change == 'restore' and
                mode in modeman.INPUT_MODES):
            tab = self.widget.currentWidget()
            if tab is not None:
                tab.data.input_mode = mode

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode):
        """Give focus to current tab if command mode was left."""
        widget = self.widget.currentWidget()
        if widget is None:
            return  # type: ignore[unreachable]
        if mode in [usertypes.KeyMode.command] + modeman.PROMPT_MODES:
            log.modes.debug("Left status-input mode, focusing {!r}".format(
                widget))
            widget.setFocus()
        if config.val.tabs.mode_on_change == 'restore':
            widget.data.input_mode = usertypes.KeyMode.normal

    @pyqtSlot(int)
    def _on_current_changed(self, idx):
        """Add prev tab to stack and leave hinting mode when focus changed."""
        mode_on_change = config.val.tabs.mode_on_change
        if idx == -1 or self.shutting_down:
            # closing the last tab (before quitting) or shutting down
            return
        tab = self.widget.widget(idx)
        if tab is None:
            log.webview.debug(  # type: ignore[unreachable]
                "on_current_changed got called with invalid index {}"
                .format(idx))
            return

        log.modes.debug("Current tab changed, focusing {!r}".format(tab))
        tab.setFocus()

        modes_to_leave = [usertypes.KeyMode.hint, usertypes.KeyMode.caret]

        mm_instance = modeman.instance(self._win_id)
        current_mode = mm_instance.mode
        log.modes.debug("Mode before tab change: {} (mode_on_change = {})"
                        .format(current_mode.name, mode_on_change))
        if mode_on_change == 'normal':
            modes_to_leave += modeman.INPUT_MODES
        for mode in modes_to_leave:
            modeman.leave(self._win_id, mode, 'tab changed', maybe=True)
        if (mode_on_change == 'restore' and
                current_mode not in modeman.PROMPT_MODES):
            modeman.enter(self._win_id, tab.data.input_mode, 'restore')
        if self._now_focused is not None:
            self.tab_deque.on_switch(self._now_focused)
        log.modes.debug("Mode after tab change: {} (mode_on_change = {})"
                        .format(current_mode.name, mode_on_change))
        self._now_focused = tab
        self.current_tab_changed.emit(tab)
        QTimer.singleShot(0, self._update_window_title)
        self._tab_insert_idx_left = self.widget.currentIndex()
        self._tab_insert_idx_right = self.widget.currentIndex() + 1

    @pyqtSlot()
    def on_cmd_return_pressed(self):
        """Set focus when the commandline closes."""
        log.modes.debug("Commandline closed, focusing {!r}".format(self))

    def _on_load_progress(self, tab, perc):
        """Adjust tab indicator on load progress."""
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        start = config.cache['colors.tabs.indicator.start']
        stop = config.cache['colors.tabs.indicator.stop']
        system = config.cache['colors.tabs.indicator.system']
        color = utils.interpolate_color(start, stop, perc, system)
        self.widget.set_tab_indicator_color(idx, color)
        self.widget.update_tab_title(idx)
        if idx == self.widget.currentIndex():
            self._update_window_title()

    def _on_load_finished(self, tab, ok):
        """Adjust tab indicator when loading finished."""
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        if ok:
            start = config.cache['colors.tabs.indicator.start']
            stop = config.cache['colors.tabs.indicator.stop']
            system = config.cache['colors.tabs.indicator.system']
            color = utils.interpolate_color(start, stop, 100, system)
        else:
            color = config.cache['colors.tabs.indicator.error']
        self.widget.set_tab_indicator_color(idx, color)
        if idx == self.widget.currentIndex():
            tab.private_api.handle_auto_insert_mode(ok)

    @pyqtSlot()
    def _on_scroll_pos_changed(self):
        """Update tab and window title when scroll position changed."""
        idx = self.widget.currentIndex()
        if idx == -1:
            # (e.g. last tab removed)
            log.webview.debug("Not updating scroll position because index is "
                              "-1")
            return
        self._update_window_title('scroll_pos')
        self.widget.update_tab_title(idx, 'scroll_pos')

    def _on_audio_changed(self, tab, _muted):
        """Update audio field in tab when mute or recentlyAudible changed."""
        try:
            idx = self._tab_index(tab)
        except TabDeletedError:
            # We can get signals for tabs we already deleted...
            return
        self.widget.update_tab_title(idx, 'audio')
        if idx == self.widget.currentIndex():
            self._update_window_title('audio')

    def _on_renderer_process_terminated(self, tab, status, code):
        """Show an error when a renderer process terminated."""
        if status == browsertab.TerminationStatus.normal:
            return

        messages = {
            browsertab.TerminationStatus.abnormal:
                "Renderer process exited with status {}".format(code),
            browsertab.TerminationStatus.crashed:
                "Renderer process crashed",
            browsertab.TerminationStatus.killed:
                "Renderer process was killed",
            browsertab.TerminationStatus.unknown:
                "Renderer process did not start",
        }
        msg = messages[status]

        def show_error_page(html):
            tab.set_html(html)
            log.webview.error(msg)

        if qtutils.version_check('5.9', compiled=False):
            url_string = tab.url(requested=True).toDisplayString()
            error_page = jinja.render(
                'error.html', title="Error loading {}".format(url_string),
                url=url_string, error=msg)
            QTimer.singleShot(100, lambda: show_error_page(error_page))
        else:
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-58698
            message.error(msg)
            self._remove_tab(tab, crashed=True)
            if self.widget.count() == 0:
                self.tabopen(QUrl('about:blank'))

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
        point = self.widget.currentWidget().scroller.pos_px()

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

        tab = self.widget.currentWidget()

        if key.isupper():
            if key in self._global_marks:
                point, url = self._global_marks[key]

                def callback(ok):
                    """Scroll once loading finished."""
                    if ok:
                        self.cur_load_finished.disconnect(callback)
                        tab.scroller.to_point(point)

                self.load_url(url, newtab=False)
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
            tab.scroller.before_jump_requested.emit()
            tab.scroller.to_point(point)
        else:
            message.error("Mark {} is not set".format(key))
