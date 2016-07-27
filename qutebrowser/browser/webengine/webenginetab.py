# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# FIXME:qtwebengine remove this once the stubs are gone
# pylint: disable=unused-variable

"""Wrapper over a QWebEngineView."""

from PyQt5.QtCore import pyqtSlot, Qt, QEvent, QPoint
from PyQt5.QtGui import QKeyEvent, QIcon
from PyQt5.QtWidgets import QApplication
# pylint: disable=no-name-in-module,import-error,useless-suppression
from PyQt5.QtWebEngineWidgets import QWebEnginePage
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.browser import browsertab
from qutebrowser.browser.webengine import webview
from qutebrowser.utils import usertypes, qtutils, log, utils


class WebEnginePrinting(browsertab.AbstractPrinting):

    """QtWebEngine implementations related to printing."""

    def check_pdf_support(self):
        if not hasattr(self._widget.page(), 'printToPdf'):
            raise browsertab.WebTabError(
                "Printing to PDF is unsupported with QtWebEngine on Qt > 5.7")

    def check_printer_support(self):
        raise browsertab.WebTabError(
            "Printing is unsupported with QtWebEngine")

    def to_pdf(self, filename):
        self._widget.page().printToPdf(filename)

    def to_printer(self, printer):
        # Should never be called
        assert False


class WebEngineSearch(browsertab.AbstractSearch):

    """QtWebEngine implementations related to searching on the page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flags = QWebEnginePage.FindFlags(0)

    def _find(self, text, flags, cb=None):
        """Call findText on the widget with optional callback."""
        if cb is None:
            self._widget.findText(text, flags)
        else:
            self._widget.findText(text, flags, cb)

    def search(self, text, *, ignore_case=False, reverse=False,
               result_cb=None):
        flags = QWebEnginePage.FindFlags(0)
        if ignore_case == 'smart':
            if not text.islower():
                flags |= QWebEnginePage.FindCaseSensitively
        elif not ignore_case:
            flags |= QWebEnginePage.FindCaseSensitively
        if reverse:
            flags |= QWebEnginePage.FindBackward

        self.text = text
        self._flags = flags
        self._find(text, flags, result_cb)

    def clear(self):
        self._widget.findText('')

    def prev_result(self, *, result_cb=None):
        # The int() here makes sure we get a copy of the flags.
        flags = QWebEnginePage.FindFlags(int(self._flags))
        if flags & QWebEnginePage.FindBackward:
            flags &= ~QWebEnginePage.FindBackward
        else:
            flags |= QWebEnginePage.FindBackward
        self._find(self.text, self._flags, result_cb)

    def next_result(self, *, result_cb=None):
        self._find(self.text, self._flags, result_cb)


class WebEngineCaret(browsertab.AbstractCaret):

    """QtWebEngine implementations related to moving the cursor/selection."""

    @pyqtSlot(usertypes.KeyMode)
    def _on_mode_entered(self, mode):
        log.stub()

    @pyqtSlot(usertypes.KeyMode)
    def _on_mode_left(self):
        log.stub()

    def move_to_next_line(self, count=1):
        log.stub()

    def move_to_prev_line(self, count=1):
        log.stub()

    def move_to_next_char(self, count=1):
        log.stub()

    def move_to_prev_char(self, count=1):
        log.stub()

    def move_to_end_of_word(self, count=1):
        log.stub()

    def move_to_next_word(self, count=1):
        log.stub()

    def move_to_prev_word(self, count=1):
        log.stub()

    def move_to_start_of_line(self):
        log.stub()

    def move_to_end_of_line(self):
        log.stub()

    def move_to_start_of_next_block(self, count=1):
        log.stub()

    def move_to_start_of_prev_block(self, count=1):
        log.stub()

    def move_to_end_of_next_block(self, count=1):
        log.stub()

    def move_to_end_of_prev_block(self, count=1):
        log.stub()

    def move_to_start_of_document(self):
        log.stub()

    def move_to_end_of_document(self):
        log.stub()

    def toggle_selection(self):
        log.stub()

    def drop_selection(self):
        log.stub()

    def has_selection(self):
        return self._widget.hasSelection()

    def selection(self, html=False):
        if html:
            raise NotImplementedError
        return self._widget.selectedText()

    def follow_selected(self, *, tab=False):
        log.stub()


class WebEngineScroller(browsertab.AbstractScroller):

    """QtWebEngine implementations related to scrolling."""

    def __init__(self, tab, parent=None):
        super().__init__(tab, parent)
        self._pos_perc = (None, None)
        self._pos_px = QPoint()

    def _init_widget(self, widget):
        super()._init_widget(widget)
        page = widget.page()
        try:
            page.scrollPositionChanged.connect(
                self._on_scroll_pos_changed)
        except AttributeError:
            log.stub('scrollPositionChanged, on Qt < 5.7')
        self._on_scroll_pos_changed()

    def _key_press(self, key, count=1):
        # FIXME:qtwebengine Abort scrolling if the minimum/maximum was reached.
        press_evt = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, 0, 0, 0)
        release_evt = QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier, 0, 0, 0)
        recipient = self._widget.focusProxy()
        for _ in range(count):
            # If we get a segfault here, we might want to try sendEvent
            # instead.
            QApplication.postEvent(recipient, press_evt)
            QApplication.postEvent(recipient, release_evt)

    @pyqtSlot()
    def _on_scroll_pos_changed(self):
        """Update the scroll position attributes when it changed."""
        def update_scroll_pos(jsret):
            """Callback after getting scroll position via JS."""
            assert isinstance(jsret, dict), jsret
            self._pos_perc = (jsret['perc']['x'], jsret['perc']['y'])
            self._pos_px = QPoint(jsret['px']['x'], jsret['px']['y'])
            self.perc_changed.emit(*self._pos_perc)

        js_code = """
            {scroll_js}
            scroll_pos();
        """.format(scroll_js=utils.read_file('javascript/scroll.js'))
        self._tab.run_js_async(js_code, update_scroll_pos)

    def pos_px(self):
        return self._pos_px

    def pos_perc(self):
        return self._pos_perc

    def to_perc(self, x=None, y=None):
        js_code = """
            {scroll_js}
            scroll_to_perc({x}, {y});
        """.format(scroll_js=utils.read_file('javascript/scroll.js'),
                   x='undefined' if x is None else x,
                   y='undefined' if y is None else y)
        self._tab.run_js_async(js_code)

    def to_point(self, point):
        self._tab.run_js_async("window.scroll({x}, {y});".format(
            x=point.x(), y=point.y()))

    def delta(self, x=0, y=0):
        self._tab.run_js_async("window.scrollBy({x}, {y});".format(x=x, y=y))

    def delta_page(self, x=0, y=0):
        js_code = """
            {scroll_js}
            scroll_delta_page({x}, {y});
        """.format(scroll_js=utils.read_file('javascript/scroll.js'), x=x, y=y)
        self._tab.run_js_async(js_code)

    def up(self, count=1):
        self._key_press(Qt.Key_Up, count)

    def down(self, count=1):
        self._key_press(Qt.Key_Down, count)

    def left(self, count=1):
        self._key_press(Qt.Key_Left, count)

    def right(self, count=1):
        self._key_press(Qt.Key_Right, count)

    def top(self):
        self._key_press(Qt.Key_Home)

    def bottom(self):
        self._key_press(Qt.Key_End)

    def page_up(self, count=1):
        self._key_press(Qt.Key_PageUp, count)

    def page_down(self, count=1):
        self._key_press(Qt.Key_PageDown, count)

    def at_top(self):
        return self.pos_px().y() == 0

    def at_bottom(self):
        log.stub()


class WebEngineHistory(browsertab.AbstractHistory):

    """QtWebEngine implementations related to page history."""

    def current_idx(self):
        return self._history.currentItemIndex()

    def back(self):
        self._history.back()

    def forward(self):
        self._history.forward()

    def can_go_back(self):
        return self._history.canGoBack()

    def can_go_forward(self):
        return self._history.canGoForward()

    def serialize(self):
        return qtutils.serialize(self._history)

    def deserialize(self, data):
        return qtutils.deserialize(data, self._history)

    def load_items(self, items):
        log.stub()


class WebEngineZoom(browsertab.AbstractZoom):

    """QtWebEngine implementations related to zooming."""

    def _set_factor_internal(self, factor):
        self._widget.setZoomFactor(factor)

    def factor(self):
        return self._widget.zoomFactor()


class WebEngineTab(browsertab.AbstractTab):

    """A QtWebEngine tab in the browser."""

    def __init__(self, win_id, mode_manager, parent=None):
        super().__init__(win_id)
        widget = webview.WebEngineView()
        self.history = WebEngineHistory(self)
        self.scroller = WebEngineScroller(self, parent=self)
        self.caret = WebEngineCaret(win_id=win_id, mode_manager=mode_manager,
                                    tab=self, parent=self)
        self.zoom = WebEngineZoom(win_id=win_id, parent=self)
        self.search = WebEngineSearch(parent=self)
        self.printing = WebEnginePrinting()
        self._set_widget(widget)
        self._connect_signals()
        self.backend = usertypes.Backend.QtWebEngine

    def openurl(self, url):
        self._openurl_prepare(url)
        self._widget.load(url)

    def url(self):
        return self._widget.url()

    def dump_async(self, callback, *, plain=False):
        if plain:
            self._widget.page().toPlainText(callback)
        else:
            self._widget.page().toHtml(callback)

    def run_js_async(self, code, callback=None):
        if callback is None:
            self._widget.page().runJavaScript(code)
        else:
            self._widget.page().runJavaScript(code, callback)

    def run_js_blocking(self, code):
        unset = object()
        loop = qtutils.EventLoop()
        js_ret = unset

        def js_cb(val):
            """Handle return value from JS and stop blocking."""
            nonlocal js_ret
            js_ret = val
            loop.quit()

        self.run_js_async(code, js_cb)
        loop.exec_()  # blocks until loop.quit() in js_cb
        assert js_ret is not unset

        return js_ret

    def shutdown(self):
        log.stub()

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

    def icon(self):
        try:
            return self._widget.icon()
        except AttributeError:
            log.stub('on Qt < 5.7')
            return QIcon()

    def set_html(self, html, base_url):
        # FIXME:qtwebengine
        # check this and raise an exception if too big:
        # Warning: The content will be percent encoded before being sent to the
        # renderer via IPC. This may increase its size. The maximum size of the
        # percent encoded content is 2 megabytes minus 30 bytes.
        self._widget.setHtml(html, base_url)

    def clear_ssl_errors(self):
        log.stub()

    def _connect_signals(self):
        view = self._widget
        page = view.page()
        page.windowCloseRequested.connect(self.window_close_requested)
        page.linkHovered.connect(self.link_hovered)
        page.loadProgress.connect(self._on_load_progress)
        page.loadStarted.connect(self._on_load_started)
        view.titleChanged.connect(self.title_changed)
        view.urlChanged.connect(self._on_url_changed)
        page.loadFinished.connect(self._on_load_finished)
        page.certificate_error.connect(self._on_ssl_errors)
        try:
            view.iconChanged.connect(self.icon_changed)
        except AttributeError:
            log.stub('iconChanged, on Qt < 5.7')
        try:
            page.contentsSizeChanged.connect(self.contents_size_changed)
        except AttributeError:
            log.stub('contentsSizeChanged, on Qt < 5.7')
