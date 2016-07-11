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
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication
# pylint: disable=no-name-in-module,import-error,useless-suppression
from PyQt5.QtWebEngineWidgets import QWebEnginePage
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.browser import browsertab
from qutebrowser.browser.webengine import webview
from qutebrowser.utils import usertypes, qtutils, log


class WebEngineSearch(browsertab.AbstractSearch):

    """QtWebEngine implementations related to searching on the page."""

    def search(self, text, *, ignore_case=False, wrap=False, reverse=False):
        log.stub()

    def clear(self):
        log.stub()

    def prev_result(self):
        log.stub()

    def next_result(self):
        log.stub()


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

    def pos_px(self):
        log.stub()
        return QPoint(0, 0)

    def pos_perc(self):
        page = self._widget.page()
        try:
            size = page.contentsSize()
            pos = page.scrollPosition()
        except AttributeError:
            # Added in Qt 5.7
            log.stub('on Qt < 5.7')
            return (None, None)
        else:
            # FIXME:qtwebengine is this correct?
            perc_x = 100 / size.width() * pos.x()
            perc_y = 100 / size.height() * pos.y()
            return (perc_x, perc_y)

    def to_perc(self, x=None, y=None):
        log.stub()

    def to_point(self, point):
        log.stub()

    def delta(self, x=0, y=0):
        log.stub()

    def delta_page(self, x=0, y=0):
        log.stub()

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
        log.stub()

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
        self.scroll = WebEngineScroller()
        self.caret = WebEngineCaret(win_id=win_id, mode_manager=mode_manager,
                                    tab=self, parent=self)
        self.zoom = WebEngineZoom(win_id=win_id, parent=self)
        self.search = WebEngineSearch(parent=self)
        self._set_widget(widget)
        self._connect_signals()
        self.backend = usertypes.Backend.QtWebEngine

    def openurl(self, url):
        self._widget.load(url)

    def url(self):
        return self._widget.url()

    def load_status(self):
        log.stub()
        return usertypes.LoadStatus.success

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
        return self._widget.icon()

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
        page.loadFinished.connect(self.load_finished)
        # FIXME:qtwebengine stub this?
        # view.iconChanged.connect(self.icon_changed)
        # view.scroll.pos_changed.connect(self.scroll.perc_changed)
        # view.url_text_changed.connect(self.url_text_changed)
        # view.load_status_changed.connect(self.load_status_changed)
