# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Wrapper over a QWebEngineView."""

import math
import functools
import dataclasses
import re
import html as html_utils
from typing import cast, Union, Optional

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QPoint, QPointF, QUrl, QObject
from PyQt5.QtNetwork import QAuthenticator
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineScript, QWebEngineHistory

from qutebrowser.config import config
from qutebrowser.browser import browsertab, eventfilter, shared, webelem, greasemonkey
from qutebrowser.browser.webengine import (webview, webengineelem, tabhistory,
                                           webenginesettings, certificateerror,
                                           webengineinspector)

from qutebrowser.utils import (usertypes, qtutils, log, javascript, utils,
                               resources, message, jinja, debug, version)
from qutebrowser.qt import sip
from qutebrowser.misc import objects, miscwidgets


# Mapping worlds from usertypes.JsWorld to QWebEngineScript world IDs.
_JS_WORLD_MAP = {
    usertypes.JsWorld.main: QWebEngineScript.MainWorld,
    usertypes.JsWorld.application: QWebEngineScript.ApplicationWorld,
    usertypes.JsWorld.user: QWebEngineScript.UserWorld,
    usertypes.JsWorld.jseval: QWebEngineScript.UserWorld + 1,
}


class WebEngineAction(browsertab.AbstractAction):

    """QtWebEngine implementations related to web actions."""

    action_class = QWebEnginePage
    action_base = QWebEnginePage.WebAction

    def exit_fullscreen(self):
        self._widget.triggerPageAction(QWebEnginePage.ExitFullScreen)

    def save_page(self):
        """Save the current page."""
        self._widget.triggerPageAction(QWebEnginePage.SavePage)

    def show_source(self, pygments=False):
        if pygments:
            self._show_source_pygments()
            return

        self._widget.triggerPageAction(QWebEnginePage.ViewSource)


class WebEnginePrinting(browsertab.AbstractPrinting):

    """QtWebEngine implementations related to printing."""

    def check_pdf_support(self):
        pass

    def check_preview_support(self):
        raise browsertab.WebTabError(
            "Print previews are unsupported with QtWebEngine")

    def to_pdf(self, filename):
        self._widget.page().printToPdf(filename)

    def to_printer(self, printer, callback=None):
        if callback is None:
            callback = lambda _ok: None
        self._widget.page().print(printer, callback)


class _WebEngineSearchWrapHandler:

    """QtWebEngine implementations related to wrapping when searching.

    Attributes:
        flag_wrap: An additional flag indicating whether the last search
                   used wrapping.
        _active_match: The 1-based index of the currently active match
                       on the page.
        _total_matches: The total number of search matches on the page.
        _nowrap_available: Whether the functionality to prevent wrapping
                           is available.
    """

    def __init__(self):
        self._active_match = 0
        self._total_matches = 0
        self.flag_wrap = True
        self._nowrap_available = False

    def connect_signal(self, page):
        """Connect to the findTextFinished signal of the page.

        Args:
            page: The QtWebEnginePage to connect to this handler.
        """
        if not qtutils.version_check("5.14"):
            return

        try:
            # pylint: disable=unused-import
            from PyQt5.QtWebEngineCore import QWebEngineFindTextResult
        except ImportError:
            # WORKAROUND for some odd PyQt/packaging bug where the
            # findTextResult signal is available, but QWebEngineFindTextResult
            # is not. Seems to happen on e.g. Gentoo.
            log.webview.warning("Could not import QWebEngineFindTextResult "
                                "despite running on Qt 5.14. You might need "
                                "to rebuild PyQtWebEngine.")
            return

        page.findTextFinished.connect(self._store_match_data)
        self._nowrap_available = True

    def _store_match_data(self, result):
        """Store information on the last match.

        The information will be checked against when wrapping is turned off.

        Args:
            result: A FindTextResult passed by the findTextFinished signal.
        """
        self._active_match = result.activeMatch()
        self._total_matches = result.numberOfMatches()
        log.webview.debug("Active search match: {}/{}"
                          .format(self._active_match, self._total_matches))

    def reset_match_data(self):
        """Reset match information.

        Stale information could lead to next_result or prev_result misbehaving.
        """
        self._active_match = 0
        self._total_matches = 0

    def prevent_wrapping(self, *, going_up):
        """Prevent wrapping if possible and required.

        Returns True if a wrap was prevented and False if not.

        Args:
            going_up: Whether the search would scroll the page up or down.
        """
        if (not self._nowrap_available or
                self.flag_wrap or self._total_matches == 0):
            return False
        elif going_up and self._active_match == 1:
            message.info("Search hit TOP")
            return True
        elif not going_up and self._active_match == self._total_matches:
            message.info("Search hit BOTTOM")
            return True
        else:
            return False


class WebEngineSearch(browsertab.AbstractSearch):

    """QtWebEngine implementations related to searching on the page.

    Attributes:
        _flags: The QWebEnginePage.FindFlags of the last search.
        _pending_searches: How many searches have been started but not called
                           back yet.
    """

    def __init__(self, tab, parent=None):
        super().__init__(tab, parent)
        self._flags = self._empty_flags()
        self._pending_searches = 0
        # The API necessary to stop wrapping was added in this version
        self._wrap_handler = _WebEngineSearchWrapHandler()

    def _empty_flags(self):
        return QWebEnginePage.FindFlags(0)  # type: ignore[call-overload]

    def connect_signals(self):
        self._wrap_handler.connect_signal(self._widget.page())

    def _find(self, text, flags, callback, caller):
        """Call findText on the widget."""
        self.search_displayed = True
        self._pending_searches += 1

        def wrapped_callback(found):
            """Wrap the callback to do debug logging."""
            self._pending_searches -= 1
            if self._pending_searches > 0:
                # See https://github.com/qutebrowser/qutebrowser/issues/2442
                # and https://github.com/qt/qtwebengine/blob/5.10/src/core/web_contents_adapter.cpp#L924-L934
                log.webview.debug("Ignoring cancelled search callback with "
                                  "{} pending searches".format(
                                      self._pending_searches))
                return

            if sip.isdeleted(self._widget):
                # This happens when starting a search, and closing the tab
                # before results arrive.
                log.webview.debug("Ignoring finished search for deleted "
                                  "widget")
                return

            found_text = 'found' if found else "didn't find"
            if flags:
                flag_text = 'with flags {}'.format(debug.qflags_key(
                    QWebEnginePage, flags, klass=QWebEnginePage.FindFlag))
            else:
                flag_text = ''
            log.webview.debug(' '.join([caller, found_text, text, flag_text])
                              .strip())

            if callback is not None:
                callback(found)
            self.finished.emit(found)

        self._widget.page().findText(text, flags, wrapped_callback)

    def search(self, text, *, ignore_case=usertypes.IgnoreCase.never,
               reverse=False, wrap=True, result_cb=None):
        # Don't go to next entry on duplicate search
        if self.text == text and self.search_displayed:
            log.webview.debug("Ignoring duplicate search request"
                              " for {}".format(text))
            return

        self.text = text
        self._flags = self._empty_flags()
        self._wrap_handler.reset_match_data()
        self._wrap_handler.flag_wrap = wrap
        if self._is_case_sensitive(ignore_case):
            self._flags |= QWebEnginePage.FindCaseSensitively
        if reverse:
            self._flags |= QWebEnginePage.FindBackward

        self._find(text, self._flags, result_cb, 'search')

    def clear(self):
        if self.search_displayed:
            self.cleared.emit()
        self.search_displayed = False
        self._wrap_handler.reset_match_data()
        self._widget.page().findText('')

    def prev_result(self, *, result_cb=None):
        # The int() here makes sure we get a copy of the flags.
        flags = QWebEnginePage.FindFlags(
            int(self._flags))  # type: ignore[call-overload]
        if flags & QWebEnginePage.FindBackward:
            if self._wrap_handler.prevent_wrapping(going_up=False):
                return
            flags &= ~QWebEnginePage.FindBackward
        else:
            if self._wrap_handler.prevent_wrapping(going_up=True):
                return
            flags |= QWebEnginePage.FindBackward
        self._find(self.text, flags, result_cb, 'prev_result')

    def next_result(self, *, result_cb=None):
        going_up = self._flags & QWebEnginePage.FindBackward
        if self._wrap_handler.prevent_wrapping(going_up=going_up):
            return
        self._find(self.text, self._flags, result_cb, 'next_result')


class WebEngineCaret(browsertab.AbstractCaret):

    """QtWebEngine implementations related to moving the cursor/selection."""

    _tab: 'WebEngineTab'

    def _flags(self):
        """Get flags to pass to JS."""
        flags = set()
        if utils.is_windows:
            flags.add('windows')
        return list(flags)

    @pyqtSlot(usertypes.KeyMode)
    def _on_mode_entered(self, mode):
        if mode != usertypes.KeyMode.caret:
            return

        if self._tab.search.search_displayed:
            # We are currently in search mode.
            # convert the search to a blue selection so we can operate on it
            self._tab.search.clear()

        self._tab.run_js_async(
            javascript.assemble('caret', 'setFlags', self._flags()))

        self._js_call('setInitialCursor', callback=self._selection_cb)

    def _selection_cb(self, enabled):
        """Emit selection_toggled based on setInitialCursor."""
        if self._mode_manager.mode != usertypes.KeyMode.caret:
            log.webview.debug("Ignoring selection cb due to mode change.")
            return
        if enabled is None:
            log.webview.debug("Ignoring selection status None")
            return
        if enabled:
            self.selection_toggled.emit(browsertab.SelectionState.normal)
        else:
            self.selection_toggled.emit(browsertab.SelectionState.none)

    @pyqtSlot(usertypes.KeyMode)
    def _on_mode_left(self, mode):
        if mode != usertypes.KeyMode.caret:
            return

        self.drop_selection()
        self._js_call('disableCaret')

    def move_to_next_line(self, count=1):
        self._js_call('moveDown', count)

    def move_to_prev_line(self, count=1):
        self._js_call('moveUp', count)

    def move_to_next_char(self, count=1):
        self._js_call('moveRight', count)

    def move_to_prev_char(self, count=1):
        self._js_call('moveLeft', count)

    def move_to_end_of_word(self, count=1):
        self._js_call('moveToEndOfWord', count)

    def move_to_next_word(self, count=1):
        self._js_call('moveToNextWord', count)

    def move_to_prev_word(self, count=1):
        self._js_call('moveToPreviousWord', count)

    def move_to_start_of_line(self):
        self._js_call('moveToStartOfLine')

    def move_to_end_of_line(self):
        self._js_call('moveToEndOfLine')

    def move_to_start_of_next_block(self, count=1):
        self._js_call('moveToStartOfNextBlock', count)

    def move_to_start_of_prev_block(self, count=1):
        self._js_call('moveToStartOfPrevBlock', count)

    def move_to_end_of_next_block(self, count=1):
        self._js_call('moveToEndOfNextBlock', count)

    def move_to_end_of_prev_block(self, count=1):
        self._js_call('moveToEndOfPrevBlock', count)

    def move_to_start_of_document(self):
        self._js_call('moveToStartOfDocument')

    def move_to_end_of_document(self):
        self._js_call('moveToEndOfDocument')

    def toggle_selection(self, line=False):
        self._js_call('toggleSelection', line,
                      callback=self._toggle_sel_translate)

    def drop_selection(self):
        self._js_call('dropSelection')

    def selection(self, callback):
        # Not using selectedText() as WORKAROUND for
        # https://bugreports.qt.io/browse/QTBUG-53134
        # Even on Qt 5.10 selectedText() seems to work poorly, see
        # https://github.com/qutebrowser/qutebrowser/issues/3523
        self._tab.run_js_async(javascript.assemble('caret', 'getSelection'),
                               callback)

    def reverse_selection(self):
        self._js_call('reverseSelection')

    def _follow_selected_cb_wrapped(self, js_elem, tab):
        try:
            self._follow_selected_cb(js_elem, tab)
        finally:
            self.follow_selected_done.emit()

    def _follow_selected_cb(self, js_elem, tab):
        """Callback for javascript which clicks the selected element.

        Args:
            js_elem: The element serialized from javascript.
            tab: Open in a new tab.
        """
        if js_elem is None:
            return

        if js_elem == "focused":
            # we had a focused element, not a selected one. Just send <enter>
            self._follow_enter(tab)
            return

        assert isinstance(js_elem, dict), js_elem
        elem = webengineelem.WebEngineElement(js_elem, tab=self._tab)
        if tab:
            click_type = usertypes.ClickTarget.tab
        else:
            click_type = usertypes.ClickTarget.normal

        # Only click if we see a link
        if elem.is_link():
            log.webview.debug("Found link in selection, clicking. ClickTarget "
                              "{}, elem {}".format(click_type, elem))
            try:
                elem.click(click_type)
            except webelem.Error as e:
                message.error(str(e))

    def follow_selected(self, *, tab=False):
        if self._tab.search.search_displayed:
            # We are currently in search mode.
            # let's click the link via a fake-click
            self._tab.search.clear()

            log.webview.debug("Clicking a searched link via fake key press.")
            # send a fake enter, clicking the orange selection box
            self._follow_enter(tab)
        else:
            # click an existing blue selection
            js_code = javascript.assemble('webelem',
                                          'find_selected_focused_link')
            self._tab.run_js_async(
                js_code,
                lambda jsret: self._follow_selected_cb_wrapped(jsret, tab))

    def _js_call(self, command, *args, callback=None):
        code = javascript.assemble('caret', command, *args)
        self._tab.run_js_async(code, callback)

    def _toggle_sel_translate(self, state_str):
        if self._mode_manager.mode != usertypes.KeyMode.caret:
            # This may happen if the user switches to another mode after
            # `:selection-toggle` is executed and before this callback function
            # is asynchronously called.
            log.misc.debug("Ignoring caret selection callback in {}".format(
                utils.pyenum_str(self._mode_manager.mode)))
            return
        if state_str is None:
            message.error("Error toggling caret selection")
            return
        state = browsertab.SelectionState[state_str]
        self.selection_toggled.emit(state)


class WebEngineScroller(browsertab.AbstractScroller):

    """QtWebEngine implementations related to scrolling."""

    def __init__(self, tab, parent=None):
        super().__init__(tab, parent)
        self._pos_perc = (0, 0)
        self._pos_px = QPoint()
        self._at_bottom = False

    def _init_widget(self, widget):
        super()._init_widget(widget)
        page = widget.page()
        page.scrollPositionChanged.connect(self._update_pos)

    def _repeated_key_press(self, key, count=1, modifier=Qt.NoModifier):
        """Send count fake key presses to this scroller's WebEngineTab."""
        for _ in range(min(count, 1000)):
            self._tab.fake_key_press(key, modifier)

    @pyqtSlot(QPointF)
    def _update_pos(self, pos):
        """Update the scroll position attributes when it changed."""
        self._pos_px = pos.toPoint()
        contents_size = self._widget.page().contentsSize()

        scrollable_x = contents_size.width() - self._widget.width()
        if scrollable_x == 0:
            perc_x = 0
        else:
            try:
                perc_x = min(100, round(100 / scrollable_x * pos.x()))
            except ValueError:
                # https://github.com/qutebrowser/qutebrowser/issues/3219
                log.misc.debug("Got ValueError for perc_x!")
                log.misc.debug("contents_size.width(): {}".format(
                    contents_size.width()))
                log.misc.debug("self._widget.width(): {}".format(
                    self._widget.width()))
                log.misc.debug("scrollable_x: {}".format(scrollable_x))
                log.misc.debug("pos.x(): {}".format(pos.x()))
                raise

        scrollable_y = contents_size.height() - self._widget.height()
        if scrollable_y == 0:
            perc_y = 0
        else:
            try:
                perc_y = min(100, round(100 / scrollable_y * pos.y()))
            except ValueError:
                # https://github.com/qutebrowser/qutebrowser/issues/3219
                log.misc.debug("Got ValueError for perc_y!")
                log.misc.debug("contents_size.height(): {}".format(
                    contents_size.height()))
                log.misc.debug("self._widget.height(): {}".format(
                    self._widget.height()))
                log.misc.debug("scrollable_y: {}".format(scrollable_y))
                log.misc.debug("pos.y(): {}".format(pos.y()))
                raise

        self._at_bottom = math.ceil(pos.y()) >= scrollable_y

        if (self._pos_perc != (perc_x, perc_y) or
                'no-scroll-filtering' in objects.debug_flags):
            self._pos_perc = perc_x, perc_y
            self.perc_changed.emit(*self._pos_perc)

    def pos_px(self):
        return self._pos_px

    def pos_perc(self):
        return self._pos_perc

    def to_perc(self, x=None, y=None):
        js_code = javascript.assemble('scroll', 'to_perc', x, y)
        self._tab.run_js_async(js_code)

    def to_point(self, point):
        js_code = javascript.assemble('window', 'scroll', point.x(), point.y())
        self._tab.run_js_async(js_code)

    def to_anchor(self, name):
        url = self._tab.url()
        url.setFragment(name)
        self._tab.load_url(url)

    def delta(self, x=0, y=0):
        self._tab.run_js_async(javascript.assemble('window', 'scrollBy', x, y))

    def delta_page(self, x=0, y=0):
        js_code = javascript.assemble('scroll', 'delta_page', x, y)
        self._tab.run_js_async(js_code)

    def up(self, count=1):
        self._repeated_key_press(Qt.Key_Up, count)

    def down(self, count=1):
        self._repeated_key_press(Qt.Key_Down, count)

    def left(self, count=1):
        self._repeated_key_press(Qt.Key_Left, count)

    def right(self, count=1):
        self._repeated_key_press(Qt.Key_Right, count)

    def top(self):
        self._tab.fake_key_press(Qt.Key_Home)

    def bottom(self):
        self._tab.fake_key_press(Qt.Key_End)

    def page_up(self, count=1):
        self._repeated_key_press(Qt.Key_PageUp, count)

    def page_down(self, count=1):
        self._repeated_key_press(Qt.Key_PageDown, count)

    def at_top(self):
        return self.pos_px().y() == 0

    def at_bottom(self):
        return self._at_bottom


class WebEngineHistoryPrivate(browsertab.AbstractHistoryPrivate):

    """History-related methods which are not part of the extension API."""

    def __init__(self, tab: 'WebEngineTab') -> None:
        self._tab = tab
        self._history = cast(QWebEngineHistory, None)

    def serialize(self):
        return qtutils.serialize(self._history)

    def deserialize(self, data):
        qtutils.deserialize(data, self._history)

    def _load_items_workaround(self, items):
        """WORKAROUND for session loading not working on Qt 5.15.

        Just load the current URL, see
        https://github.com/qutebrowser/qutebrowser/issues/5359
        """
        if not items:
            return

        for i, item in enumerate(items):
            if item.active:
                cur_idx = i
                break

        url = items[cur_idx].url
        if (url.scheme(), url.host()) == ('qute', 'back') and cur_idx >= 1:
            url = items[cur_idx - 1].url

        self._tab.load_url(url)

    def load_items(self, items):
        webengine_version = version.qtwebengine_versions().webengine
        if webengine_version >= utils.VersionNumber(5, 15):
            self._load_items_workaround(items)
            return

        if items:
            self._tab.before_load_started.emit(items[-1].url)

        stream, _data, cur_data = tabhistory.serialize(items)
        qtutils.deserialize_stream(stream, self._history)

        @pyqtSlot()
        def _on_load_finished():
            self._tab.scroller.to_point(cur_data['scroll-pos'])
            self._tab.load_finished.disconnect(_on_load_finished)

        if cur_data is not None:
            if 'zoom' in cur_data:
                self._tab.zoom.set_factor(cur_data['zoom'])
            if ('scroll-pos' in cur_data and
                    self._tab.scroller.pos_px() == QPoint(0, 0)):
                self._tab.load_finished.connect(_on_load_finished)


class WebEngineHistory(browsertab.AbstractHistory):

    """QtWebEngine implementations related to page history."""

    def __init__(self, tab):
        super().__init__(tab)
        self.private_api = WebEngineHistoryPrivate(tab)

    def __len__(self):
        return len(self._history)

    def __iter__(self):
        return iter(self._history.items())

    def current_idx(self):
        return self._history.currentItemIndex()

    def can_go_back(self):
        return self._history.canGoBack()

    def can_go_forward(self):
        return self._history.canGoForward()

    def _item_at(self, i):
        return self._history.itemAt(i)

    def _go_to_item(self, item):
        self._tab.before_load_started.emit(item.url())
        self._history.goToItem(item)

    def back_items(self):
        return self._history.backItems(self._history.count())

    def forward_items(self):
        return self._history.forwardItems(self._history.count())


class WebEngineZoom(browsertab.AbstractZoom):

    """QtWebEngine implementations related to zooming."""

    def _set_factor_internal(self, factor):
        self._widget.setZoomFactor(factor)


class WebEngineElements(browsertab.AbstractElements):

    """QtWebEngine implementations related to elements on the page."""

    _tab: 'WebEngineTab'

    def _js_cb_multiple(self, callback, error_cb, js_elems):
        """Handle found elements coming from JS and call the real callback.

        Args:
            callback: The callback to call with the found elements.
            error_cb: The callback to call in case of an error.
            js_elems: The elements serialized from javascript.
        """
        if js_elems is None:
            error_cb(webelem.Error("Unknown error while getting "
                                   "elements"))
            return
        elif not js_elems['success']:
            error_cb(webelem.Error(js_elems['error']))
            return

        elems = []
        for js_elem in js_elems['result']:
            elem = webengineelem.WebEngineElement(js_elem, tab=self._tab)
            elems.append(elem)
        callback(elems)

    def _js_cb_single(self, callback, js_elem):
        """Handle a found focus elem coming from JS and call the real callback.

        Args:
            callback: The callback to call with the found element.
                      Called with a WebEngineElement or None.
            js_elem: The element serialized from javascript.
        """
        debug_str = ('None' if js_elem is None
                     else utils.elide(repr(js_elem), 1000))
        log.webview.debug("Got element from JS: {}".format(debug_str))

        if js_elem is None:
            callback(None)
        else:
            elem = webengineelem.WebEngineElement(js_elem, tab=self._tab)
            callback(elem)

    def find_css(self, selector, callback, error_cb, *,
                 only_visible=False):
        js_code = javascript.assemble('webelem', 'find_css', selector,
                                      only_visible)
        js_cb = functools.partial(self._js_cb_multiple, callback, error_cb)
        self._tab.run_js_async(js_code, js_cb)

    def find_id(self, elem_id, callback):
        js_code = javascript.assemble('webelem', 'find_id', elem_id)
        js_cb = functools.partial(self._js_cb_single, callback)
        self._tab.run_js_async(js_code, js_cb)

    def find_focused(self, callback):
        js_code = javascript.assemble('webelem', 'find_focused')
        js_cb = functools.partial(self._js_cb_single, callback)
        self._tab.run_js_async(js_code, js_cb)

    def find_at_pos(self, pos, callback):
        assert pos.x() >= 0, pos
        assert pos.y() >= 0, pos
        pos /= self._tab.zoom.factor()
        js_code = javascript.assemble('webelem', 'find_at_pos',
                                      pos.x(), pos.y())
        js_cb = functools.partial(self._js_cb_single, callback)
        self._tab.run_js_async(js_code, js_cb)


class WebEngineAudio(browsertab.AbstractAudio):

    """QtWebEngine implementations related to audio/muting.

    Attributes:
        _overridden: Whether the user toggled muting manually.
                     If that's the case, we leave it alone.
    """

    def __init__(self, tab, parent=None):
        super().__init__(tab, parent)
        self._overridden = False

    def _connect_signals(self):
        page = self._widget.page()
        page.audioMutedChanged.connect(self.muted_changed)
        page.recentlyAudibleChanged.connect(self.recently_audible_changed)
        self._tab.url_changed.connect(self._on_url_changed)
        config.instance.changed.connect(self._on_config_changed)

    def set_muted(self, muted: bool, override: bool = False) -> None:
        was_muted = self.is_muted()
        self._overridden = override
        assert self._widget is not None
        page = self._widget.page()
        page.setAudioMuted(muted)
        if was_muted != muted and qtutils.version_check('5.15'):
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-85118
            # so that the tab title at least updates the muted indicator
            self.muted_changed.emit(muted)

    def is_muted(self):
        page = self._widget.page()
        return page.isAudioMuted()

    def is_recently_audible(self):
        page = self._widget.page()
        return page.recentlyAudible()

    @pyqtSlot(QUrl)
    def _on_url_changed(self, url):
        if self._overridden or not url.isValid():
            return
        mute = config.instance.get('content.mute', url=url)
        self.set_muted(mute)

    @config.change_filter('content.mute')
    def _on_config_changed(self):
        self._on_url_changed(self._tab.url())


class _WebEnginePermissions(QObject):

    """Handling of various permission-related signals."""

    # Using 0 as WORKAROUND for:
    # https://www.riverbankcomputing.com/pipermail/pyqt/2019-July/041903.html

    _options = {
        0: 'content.notifications.enabled',
        QWebEnginePage.Geolocation: 'content.geolocation',
        QWebEnginePage.MediaAudioCapture: 'content.media.audio_capture',
        QWebEnginePage.MediaVideoCapture: 'content.media.video_capture',
        QWebEnginePage.MediaAudioVideoCapture: 'content.media.audio_video_capture',
        QWebEnginePage.MouseLock: 'content.mouse_lock',
        QWebEnginePage.DesktopVideoCapture: 'content.desktop_capture',
        QWebEnginePage.DesktopAudioVideoCapture: 'content.desktop_capture',
    }

    _messages = {
        0: 'show notifications',
        QWebEnginePage.Geolocation: 'access your location',
        QWebEnginePage.MediaAudioCapture: 'record audio',
        QWebEnginePage.MediaVideoCapture: 'record video',
        QWebEnginePage.MediaAudioVideoCapture: 'record audio/video',
        QWebEnginePage.MouseLock: 'hide your mouse pointer',
        QWebEnginePage.DesktopVideoCapture: 'capture your desktop',
        QWebEnginePage.DesktopAudioVideoCapture: 'capture your desktop and audio',
    }

    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self._tab = tab
        self._widget = cast(QWidget, None)
        assert self._options.keys() == self._messages.keys()

    def connect_signals(self):
        """Connect related signals from the QWebEnginePage."""
        page = self._widget.page()
        page.fullScreenRequested.connect(
            self._on_fullscreen_requested)
        page.featurePermissionRequested.connect(
            self._on_feature_permission_requested)

        page.quotaRequested.connect(self._on_quota_requested)
        page.registerProtocolHandlerRequested.connect(
            self._on_register_protocol_handler_requested)

    @pyqtSlot('QWebEngineFullScreenRequest')
    def _on_fullscreen_requested(self, request):
        request.accept()
        on = request.toggleOn()

        self._tab.data.fullscreen = on
        self._tab.fullscreen_requested.emit(on)
        if on:
            timeout = config.val.content.fullscreen.overlay_timeout
            if timeout != 0:
                notif = miscwidgets.FullscreenNotification(self._widget)
                notif.set_timeout(timeout)
                notif.show()

    @pyqtSlot(QUrl, 'QWebEnginePage::Feature')
    def _on_feature_permission_requested(self, url, feature):
        """Ask the user for approval for geolocation/media/etc.."""
        page = self._widget.page()
        grant_permission = functools.partial(
            page.setFeaturePermission, url, feature,
            QWebEnginePage.PermissionGrantedByUser)
        deny_permission = functools.partial(
            page.setFeaturePermission, url, feature,
            QWebEnginePage.PermissionDeniedByUser)

        permission_str = debug.qenum_key(QWebEnginePage, feature)

        if not url.isValid():
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-85116
            is_qtbug = (qtutils.version_check('5.15.0',
                                              compiled=False,
                                              exact=True) and
                        self._tab.is_private and
                        feature == QWebEnginePage.Notifications)
            logger = log.webview.debug if is_qtbug else log.webview.warning
            logger("Ignoring feature permission {} for invalid URL {}".format(
                permission_str, url))
            deny_permission()
            return

        if feature not in self._options:
            log.webview.error("Unhandled feature permission {}".format(
                permission_str))
            deny_permission()
            return

        if (
                feature in [QWebEnginePage.DesktopVideoCapture,
                            QWebEnginePage.DesktopAudioVideoCapture] and
                qtutils.version_check('5.13', compiled=False) and
                not qtutils.version_check('5.13.2', compiled=False)
        ):
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-78016
            log.webview.warning("Ignoring desktop sharing request due to "
                                "crashes in Qt < 5.13.2")
            deny_permission()
            return

        question = shared.feature_permission(
            url=url.adjusted(QUrl.RemovePath),
            option=self._options[feature], msg=self._messages[feature],
            yes_action=grant_permission, no_action=deny_permission,
            abort_on=[self._tab.abort_questions])

        if question is not None:
            page.featurePermissionRequestCanceled.connect(
                functools.partial(self._on_feature_permission_cancelled,
                                  question, url, feature))

    def _on_feature_permission_cancelled(self, question, url, feature,
                                         cancelled_url, cancelled_feature):
        """Slot invoked when a feature permission request was cancelled.

        To be used with functools.partial.
        """
        if url == cancelled_url and feature == cancelled_feature:
            try:
                question.abort()
            except RuntimeError:
                # The question could already be deleted, e.g. because it was
                # aborted after a loadStarted signal.
                pass

    def _on_quota_requested(self, request):
        size = utils.format_size(request.requestedSize())
        shared.feature_permission(
            url=request.origin().adjusted(QUrl.RemovePath),
            option='content.persistent_storage',
            msg='use {} of persistent storage'.format(size),
            yes_action=request.accept, no_action=request.reject,
            abort_on=[self._tab.abort_questions],
            blocking=True)

    def _on_register_protocol_handler_requested(self, request):
        shared.feature_permission(
            url=request.origin().adjusted(QUrl.RemovePath),
            option='content.register_protocol_handler',
            msg='open all {} links'.format(request.scheme()),
            yes_action=request.accept, no_action=request.reject,
            abort_on=[self._tab.abort_questions],
            blocking=True)


@dataclasses.dataclass
class _Quirk:

    filename: str
    injection_point: QWebEngineScript.InjectionPoint = (
        QWebEngineScript.DocumentCreation)
    world: QWebEngineScript.ScriptWorldId = QWebEngineScript.MainWorld
    predicate: bool = True


class _WebEngineScripts(QObject):

    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self._tab = tab
        self._widget = cast(QWidget, None)
        self._greasemonkey = greasemonkey.gm_manager

    def connect_signals(self):
        """Connect signals to our private slots."""
        config.instance.changed.connect(self._on_config_changed)

        self._tab.search.cleared.connect(functools.partial(
            self._update_stylesheet, searching=False))
        self._tab.search.finished.connect(self._update_stylesheet)

    @pyqtSlot(str)
    def _on_config_changed(self, option):
        if option in ['scrolling.bar', 'content.user_stylesheets']:
            self._init_stylesheet()
            self._update_stylesheet()

    @pyqtSlot(bool)
    def _update_stylesheet(self, searching=False):
        """Update the custom stylesheet in existing tabs."""
        css = shared.get_user_stylesheet(searching=searching)
        code = javascript.assemble('stylesheet', 'set_css', css)
        self._tab.run_js_async(code)

    def _inject_js(self, name, js_code, *,
                   world=QWebEngineScript.ApplicationWorld,
                   injection_point=QWebEngineScript.DocumentCreation,
                   subframes=False):
        """Inject the given script to run early on a page load."""
        script = QWebEngineScript()
        script.setInjectionPoint(injection_point)
        script.setSourceCode(js_code)
        script.setWorldId(world)
        script.setRunsOnSubFrames(subframes)
        script.setName(f'_qute_{name}')
        self._widget.page().scripts().insert(script)

    def _remove_js(self, name):
        """Remove an early QWebEngineScript."""
        scripts = self._widget.page().scripts()
        script = scripts.findScript(f'_qute_{name}')
        if not script.isNull():
            scripts.remove(script)

    def init(self):
        """Initialize global qutebrowser JavaScript."""
        js_code = javascript.wrap_global(
            'scripts',
            resources.read_file('javascript/scroll.js'),
            resources.read_file('javascript/webelem.js'),
            resources.read_file('javascript/caret.js'),
        )
        # FIXME:qtwebengine what about subframes=True?
        self._inject_js('js', js_code, subframes=True)
        self._init_stylesheet()

        self._greasemonkey.scripts_reloaded.connect(
            self._inject_all_greasemonkey_scripts)
        self._inject_all_greasemonkey_scripts()
        self._inject_site_specific_quirks()

    def _init_stylesheet(self):
        """Initialize custom stylesheets.

        Partially inspired by QupZilla:
        https://github.com/QupZilla/qupzilla/blob/v2.0/src/lib/app/mainapplication.cpp#L1063-L1101
        """
        self._remove_js('stylesheet')
        css = shared.get_user_stylesheet()
        js_code = javascript.wrap_global(
            'stylesheet',
            resources.read_file('javascript/stylesheet.js'),
            javascript.assemble('stylesheet', 'set_css', css),
        )
        self._inject_js('stylesheet', js_code, subframes=True)

    @pyqtSlot()
    def _inject_all_greasemonkey_scripts(self):
        scripts = self._greasemonkey.all_scripts()
        self._inject_greasemonkey_scripts(scripts)

    def _remove_all_greasemonkey_scripts(self):
        page_scripts = self._widget.page().scripts()
        for script in page_scripts.toList():
            if script.name().startswith("GM-"):
                log.greasemonkey.debug('Removing script: {}'
                                       .format(script.name()))
                removed = page_scripts.remove(script)
                assert removed, script.name()

    def _inject_greasemonkey_scripts(self, scripts):
        """Register user JavaScript files with the current tab.

        Args:
            scripts: A list of GreasemonkeyScripts.
        """
        if sip.isdeleted(self._widget):
            return

        # Since we are inserting scripts into a per-tab collection,
        # rather than just injecting scripts on page load, we need to
        # make sure we replace existing scripts, not just add new ones.
        # While, taking care not to remove any other scripts that might
        # have been added elsewhere, like the one for stylesheets.
        page_scripts = self._widget.page().scripts()
        self._remove_all_greasemonkey_scripts()

        for script in scripts:
            new_script = QWebEngineScript()

            try:
                world = int(script.jsworld)
                if not 0 <= world <= qtutils.MAX_WORLD_ID:
                    log.greasemonkey.error(
                        f"script {script.name} has invalid value for '@qute-js-world'"
                        f": {script.jsworld}, should be between 0 and "
                        f"{qtutils.MAX_WORLD_ID}")
                    continue
            except ValueError:
                try:
                    world = _JS_WORLD_MAP[usertypes.JsWorld[script.jsworld.lower()]]
                except KeyError:
                    log.greasemonkey.error(
                        f"script {script.name} has invalid value for '@qute-js-world'"
                        f": {script.jsworld}")
                    continue
            new_script.setWorldId(world)

            # Corresponds to "@run-at document-end" which is the default according to
            # https://wiki.greasespot.net/Metadata_Block#.40run-at - however,
            # QtWebEngine uses QWebEngineScript.Deferred (@run-at document-idle) as
            # default.
            #
            # NOTE that this needs to be done before setSourceCode, so that
            # QtWebEngine's parsing of GreaseMonkey tags will override it if there is a
            # @run-at comment.
            new_script.setInjectionPoint(QWebEngineScript.DocumentReady)

            new_script.setSourceCode(script.code())
            new_script.setName(f"GM-{script.name}")
            new_script.setRunsOnSubFrames(script.runs_on_sub_frames)

            if script.needs_document_end_workaround():
                log.greasemonkey.debug(
                    f"Forcing @run-at document-end for {script.name}")
                new_script.setInjectionPoint(QWebEngineScript.DocumentReady)

            log.greasemonkey.debug(f'adding script: {new_script.name()}')
            page_scripts.insert(new_script)

    def _inject_site_specific_quirks(self):
        """Add site-specific quirk scripts."""
        if not config.val.content.site_specific_quirks.enabled:
            return

        versions = version.qtwebengine_versions()
        quirks = [
            _Quirk(
                'whatsapp_web',
                injection_point=QWebEngineScript.DocumentReady,
                world=QWebEngineScript.ApplicationWorld,
            ),
            _Quirk(
                'string_replaceall',
                predicate=versions.webengine < utils.VersionNumber(5, 15, 3),
            ),
            _Quirk(
                'globalthis',
                predicate=versions.webengine < utils.VersionNumber(5, 13),
            ),
            _Quirk(
                'object_fromentries',
                predicate=versions.webengine < utils.VersionNumber(5, 13),
            )
        ]

        for quirk in quirks:
            if not quirk.predicate:
                continue
            src = resources.read_file(f'javascript/quirks/{quirk.filename}.user.js')
            name = f"js-{quirk.filename.replace('_', '-')}"
            if name not in config.val.content.site_specific_quirks.skip:
                self._inject_js(
                    f'quirk_{quirk.filename}',
                    src,
                    world=quirk.world,
                    injection_point=quirk.injection_point,
                )


class WebEngineTabPrivate(browsertab.AbstractTabPrivate):

    """QtWebEngine-related methods which aren't part of the public API."""

    def networkaccessmanager(self):
        return None

    def user_agent(self):
        return None

    def clear_ssl_errors(self):
        raise browsertab.UnsupportedOperationError

    def event_target(self):
        return self._widget.render_widget()

    def shutdown(self):
        self._tab.shutting_down.emit()
        self._tab.action.exit_fullscreen()
        self._widget.shutdown()

    def run_js_sync(self, code):
        raise browsertab.UnsupportedOperationError

    def _init_inspector(self, splitter, win_id, parent=None):
        return webengineinspector.WebEngineInspector(splitter, win_id, parent)


class WebEngineTab(browsertab.AbstractTab):

    """A QtWebEngine tab in the browser.

    Signals:
        abort_questions: Emitted when a new load started or we're shutting
            down.
    """

    abort_questions = pyqtSignal()

    def __init__(self, *, win_id, mode_manager, private, parent=None):
        super().__init__(win_id=win_id,
                         mode_manager=mode_manager,
                         private=private,
                         parent=parent)
        widget = webview.WebEngineView(tabdata=self.data, win_id=win_id,
                                       private=private)
        self.history = WebEngineHistory(tab=self)
        self.scroller = WebEngineScroller(tab=self, parent=self)
        self.caret = WebEngineCaret(mode_manager=mode_manager,
                                    tab=self, parent=self)
        self.zoom = WebEngineZoom(tab=self, parent=self)
        self.search = WebEngineSearch(tab=self, parent=self)
        self.printing = WebEnginePrinting(tab=self)
        self.elements = WebEngineElements(tab=self)
        self.action = WebEngineAction(tab=self)
        self.audio = WebEngineAudio(tab=self, parent=self)
        self.private_api = WebEngineTabPrivate(mode_manager=mode_manager,
                                               tab=self)
        self._permissions = _WebEnginePermissions(tab=self, parent=self)
        self._scripts = _WebEngineScripts(tab=self, parent=self)
        # We're assigning settings in _set_widget
        self.settings = webenginesettings.WebEngineSettings(settings=None)
        self._set_widget(widget)
        self._connect_signals()
        self.backend = usertypes.Backend.QtWebEngine
        self._child_event_filter = None
        self._saved_zoom = None
        self._scripts.init()

    def _set_widget(self, widget):
        # pylint: disable=protected-access
        super()._set_widget(widget)
        self._permissions._widget = widget
        self._scripts._widget = widget

    def _install_event_filter(self):
        fp = self._widget.focusProxy()
        if fp is not None:
            fp.installEventFilter(self._tab_event_filter)

        self._child_event_filter = eventfilter.ChildEventFilter(
            eventfilter=self._tab_event_filter,
            widget=self._widget,
            parent=self)
        self._widget.installEventFilter(self._child_event_filter)

    @pyqtSlot()
    def _restore_zoom(self):
        if sip.isdeleted(self._widget):
            # https://github.com/qutebrowser/qutebrowser/issues/3498
            return
        if self._saved_zoom is None:
            return
        self.zoom.set_factor(self._saved_zoom)
        self._saved_zoom = None

    def load_url(self, url):
        """Load the given URL in this tab.

        Arguments:
            url: The QUrl to load.
        """
        if sip.isdeleted(self._widget):
            # https://github.com/qutebrowser/qutebrowser/issues/3896
            return
        self._saved_zoom = self.zoom.factor()
        self._load_url_prepare(url)
        self._widget.load(url)

    def url(self, *, requested=False):
        page = self._widget.page()
        if requested:
            return page.requestedUrl()
        else:
            return page.url()

    def dump_async(self, callback, *, plain=False):
        if plain:
            self._widget.page().toPlainText(callback)
        else:
            self._widget.page().toHtml(callback)

    def run_js_async(self, code, callback=None, *, world=None):
        world_id_type = Union[QWebEngineScript.ScriptWorldId, int]
        if world is None:
            world_id: world_id_type = QWebEngineScript.ApplicationWorld
        elif isinstance(world, int):
            world_id = world
            if not 0 <= world_id <= qtutils.MAX_WORLD_ID:
                raise browsertab.WebTabError(
                    "World ID should be between 0 and {}"
                    .format(qtutils.MAX_WORLD_ID))
        else:
            world_id = _JS_WORLD_MAP[world]

        if callback is None:
            self._widget.page().runJavaScript(code, world_id)
        else:
            self._widget.page().runJavaScript(code, world_id, callback)

    def reload(self, *, force=False):
        if force:
            action = QWebEnginePage.ReloadAndBypassCache
        else:
            action = QWebEnginePage.Reload
        self._widget.triggerPageAction(action)

    def stop(self):
        self._widget.stop()

    def title(self):
        return self._widget.title()

    def renderer_process_pid(self) -> Optional[int]:
        page = self._widget.page()
        try:
            return page.renderProcessPid()
        except AttributeError:
            # Added in Qt 5.15
            return None

    def icon(self):
        return self._widget.icon()

    def set_html(self, html, base_url=QUrl()):
        # FIXME:qtwebengine
        # check this and raise an exception if too big:
        # Warning: The content will be percent encoded before being sent to the
        # renderer via IPC. This may increase its size. The maximum size of the
        # percent encoded content is 2 megabytes minus 30 bytes.
        self._widget.setHtml(html, base_url)

    def _show_error_page(self, url, error):
        """Show an error page in the tab."""
        log.misc.debug("Showing error page for {}".format(error))
        url_string = url.toDisplayString()
        error_page = jinja.render(
            'error.html',
            title="Error loading page: {}".format(url_string),
            url=url_string, error=error)
        self.set_html(error_page)

    @pyqtSlot()
    def _on_history_trigger(self):
        try:
            self._widget.page()
        except RuntimeError:
            # Looks like this slot can be triggered on destroyed tabs:
            # https://crashes.qutebrowser.org/view/3abffbed (Qt 5.9.1)
            # wrapped C/C++ object of type WebEngineView has been deleted
            log.misc.debug("Ignoring history trigger for destroyed tab")
            return

        url = self.url()
        requested_url = self.url(requested=True)

        # Don't save the title if it's generated from the URL
        title = self.title()
        title_url = QUrl(url)
        title_url.setScheme('')
        title_url_str = title_url.toDisplayString(
            QUrl.RemoveScheme)  # type: ignore[arg-type]
        if title == title_url_str.strip('/'):
            title = ""

        # Don't add history entry if the URL is invalid anyways
        if not url.isValid():
            log.misc.debug("Ignoring invalid URL being added to history")
            return

        self.history_item_triggered.emit(url, requested_url, title)

    @pyqtSlot(QUrl, 'QAuthenticator*', 'QString')
    def _on_proxy_authentication_required(self, url, authenticator,
                                          proxy_host):
        """Called when a proxy needs authentication."""
        msg = "<b>{}</b> requires a username and password.".format(
            html_utils.escape(proxy_host))
        urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
        answer = message.ask(
            title="Proxy authentication required", text=msg,
            mode=usertypes.PromptMode.user_pwd,
            abort_on=[self.abort_questions], url=urlstr)

        if answer is None:
            sip.assign(authenticator, QAuthenticator())
            return

        authenticator.setUser(answer.user)
        authenticator.setPassword(answer.password)

    @pyqtSlot(QUrl, 'QAuthenticator*')
    def _on_authentication_required(self, url, authenticator):
        log.network.debug("Authentication requested for {}, netrc_used {}"
                          .format(url.toDisplayString(), self.data.netrc_used))

        netrc_success = False
        if not self.data.netrc_used:
            self.data.netrc_used = True
            netrc_success = shared.netrc_authentication(url, authenticator)

        if not netrc_success:
            log.network.debug("Asking for credentials")
            answer = shared.authentication_required(
                url, authenticator, abort_on=[self.abort_questions])
        if not netrc_success and answer is None:
            log.network.debug("Aborting auth")
            sip.assign(authenticator, QAuthenticator())

    @pyqtSlot()
    def _on_load_started(self):
        """Clear search when a new load is started if needed."""
        # WORKAROUND for
        # https://bugreports.qt.io/browse/QTBUG-61506
        # (seems to be back in later Qt versions as well)
        self.search.clear()
        super()._on_load_started()
        self.data.netrc_used = False

    @pyqtSlot('qint64')
    def _on_renderer_process_pid_changed(self, pid):
        log.webview.debug("Renderer process PID for tab {}: {}"
                          .format(self.tab_id, pid))

    @pyqtSlot(QWebEnginePage.RenderProcessTerminationStatus, int)
    def _on_render_process_terminated(self, status, exitcode):
        """Show an error when the renderer process terminated."""
        if (status == QWebEnginePage.AbnormalTerminationStatus and
                exitcode == 256):
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-58697
            status = QWebEnginePage.CrashedTerminationStatus

        status_map = {
            QWebEnginePage.NormalTerminationStatus:
                browsertab.TerminationStatus.normal,
            QWebEnginePage.AbnormalTerminationStatus:
                browsertab.TerminationStatus.abnormal,
            QWebEnginePage.CrashedTerminationStatus:
                browsertab.TerminationStatus.crashed,
            QWebEnginePage.KilledTerminationStatus:
                browsertab.TerminationStatus.killed,
            -1:
                browsertab.TerminationStatus.unknown,
        }
        self.renderer_process_terminated.emit(status_map[status], exitcode)

    def _error_page_workaround(self, js_enabled, html):
        """Check if we're displaying a Chromium error page.

        This gets called if we got a loadFinished(False), so we can display at
        least some error page in situations where Chromium's can't be
        displayed.

        WORKAROUND for https://bugreports.qt.io/browse/QTBUG-66643
        WORKAROUND for https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=882805
        """
        match = re.search(r'"errorCode":"([^"]*)"', html)
        if match is None:
            return

        error = match.group(1)
        log.webview.error("Load error: {}".format(error))

        missing_jst = 'jstProcess(' in html and 'jstProcess=' not in html
        if js_enabled and not missing_jst:
            return

        self._show_error_page(self.url(), error=error)

    @pyqtSlot(int)
    def _on_load_progress(self, perc: int) -> None:
        """QtWebEngine-specific loadProgress workarounds.

        WORKAROUND for https://bugreports.qt.io/browse/QTBUG-65223
        """
        super()._on_load_progress(perc)
        if (perc == 100 and
                self.load_status() != usertypes.LoadStatus.error):
            self._update_load_status(ok=True)

    @pyqtSlot(bool)
    def _on_load_finished(self, ok: bool) -> None:
        """QtWebEngine-specific loadFinished workarounds."""
        super()._on_load_finished(ok)

        if not ok:
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-65223
            self._update_load_status(ok)

            self.dump_async(functools.partial(
                self._error_page_workaround,
                self.settings.test_attribute('content.javascript.enabled')))

    @pyqtSlot(certificateerror.CertificateErrorWrapper)
    def _on_ssl_errors(self, error):
        url = error.url()
        self._insecure_hosts.add(url.host())

        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-92009
        # self.url() is not available yet and the requested URL might not match the URL
        # we get from the error - so we just apply a heuristic here.
        assert self.data.last_navigation is not None
        first_party_url = self.data.last_navigation.url

        log.network.debug("Certificate error: {}".format(error))
        log.network.debug("First party URL: {}".format(first_party_url))

        if error.is_overridable():
            error.ignore = shared.ignore_certificate_error(
                request_url=url,
                first_party_url=first_party_url,
                error=error,
                abort_on=[self.abort_questions],
            )
        else:
            log.network.error("Non-overridable certificate error: "
                              "{}".format(error))

        log.network.debug("ignore {}, URL {}, requested {}".format(
            error.ignore, url, self.url(requested=True)))

        # WORKAROUND for https://codereview.qt-project.org/c/qt/qtwebengine/+/270556
        show_non_overr_cert_error = (
            not error.is_overridable() and (
                # Affected Qt versions:
                # 5.13 before 5.13.2
                # 5.12 before 5.12.6
                # < 5.12 (which is unsupported)
                (qtutils.version_check('5.13') and
                 not qtutils.version_check('5.13.2')) or
                (qtutils.version_check('5.12') and
                 not qtutils.version_check('5.12.6'))
            )
        )

        # We can't really know when to show an error page, as the error might
        # have happened when loading some resource.
        is_resource = (
            first_party_url.isValid() and
            url.matches(first_party_url, QUrl.RemoveScheme))
        if show_non_overr_cert_error and is_resource:
            self._show_error_page(url, str(error))

    @pyqtSlot()
    def _on_print_requested(self):
        """Slot for window.print() in JS."""
        try:
            self.printing.show_dialog()
        except browsertab.WebTabError as e:
            message.error(str(e))

    @pyqtSlot(QUrl)
    def _on_url_changed(self, url: QUrl) -> None:
        """Update settings for the current URL.

        Normally this is done below in _on_navigation_request, but we also need
        to do it here as WORKAROUND for
        https://bugreports.qt.io/browse/QTBUG-77137

        Since update_for_url() is idempotent, it doesn't matter much if we end
        up doing it twice.
        """
        super()._on_url_changed(url)
        if url.isValid() and qtutils.version_check('5.13'):
            self.settings.update_for_url(url)

    @pyqtSlot(usertypes.NavigationRequest)
    def _on_navigation_request(self, navigation):
        super()._on_navigation_request(navigation)

        if not navigation.accepted or not navigation.is_main_frame:
            return

        self.settings.update_for_url(navigation.url)

    def _on_select_client_certificate(self, selection):
        """Handle client certificates.

        Currently, we simply pick the first available certificate and show an
        additional note if there are multiple matches.
        """
        certificate = selection.certificates()[0]
        text = ('<b>Subject:</b> {subj}<br/>'
                '<b>Issuer:</b> {issuer}<br/>'
                '<b>Serial:</b> {serial}'.format(
                    subj=html_utils.escape(certificate.subjectDisplayName()),
                    issuer=html_utils.escape(certificate.issuerDisplayName()),
                    serial=bytes(certificate.serialNumber()).decode('ascii')))
        if len(selection.certificates()) > 1:
            text += ('<br/><br/><b>Note:</b> Multiple matching certificates '
                     'were found, but certificate selection is not '
                     'implemented yet!')
        urlstr = selection.host().host()

        present = message.ask(
            title='Present client certificate to {}?'.format(urlstr),
            text=text,
            mode=usertypes.PromptMode.yesno,
            abort_on=[self.abort_questions],
            url=urlstr)

        if present:
            selection.select(certificate)
        else:
            selection.selectNone()

    def _connect_signals(self):
        view = self._widget
        page = view.page()

        page.windowCloseRequested.connect(self.window_close_requested)
        page.linkHovered.connect(self.link_hovered)
        page.loadProgress.connect(self._on_load_progress)
        page.loadStarted.connect(self._on_load_started)
        page.certificate_error.connect(self._on_ssl_errors)
        page.authenticationRequired.connect(self._on_authentication_required)
        page.proxyAuthenticationRequired.connect(
            self._on_proxy_authentication_required)
        page.contentsSizeChanged.connect(self.contents_size_changed)
        page.navigation_request.connect(self._on_navigation_request)
        page.printRequested.connect(self._on_print_requested)

        try:
            # pylint: disable=unused-import
            from PyQt5.QtWebEngineWidgets import (
                QWebEngineClientCertificateSelection)
        except ImportError:
            pass
        else:
            page.selectClientCertificate.connect(
                self._on_select_client_certificate)

        view.titleChanged.connect(self.title_changed)
        view.urlChanged.connect(self._on_url_changed)
        view.renderProcessTerminated.connect(
            self._on_render_process_terminated)
        view.iconChanged.connect(self.icon_changed)

        page.loadFinished.connect(self._on_history_trigger)
        page.loadFinished.connect(self._restore_zoom)
        page.loadFinished.connect(self._on_load_finished)

        try:
            page.renderProcessPidChanged.connect(self._on_renderer_process_pid_changed)
        except AttributeError:
            # Added in Qt 5.15.0
            pass

        self.shutting_down.connect(self.abort_questions)
        self.load_started.connect(self.abort_questions)

        # pylint: disable=protected-access
        self.audio._connect_signals()
        self.search.connect_signals()
        self._permissions.connect_signals()
        self._scripts.connect_signals()
