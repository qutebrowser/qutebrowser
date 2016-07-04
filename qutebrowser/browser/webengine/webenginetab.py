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

"""Wrapper over a QWebEngineView."""

from PyQt5.QtCore import pyqtSlot, Qt, QEvent
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
except ImportError:
    QWebEngineView = None
    QWebEnginePage = None

from qutebrowser.browser import tab
from qutebrowser.browser.webengine import webview
from qutebrowser.utils import usertypes, qtutils


class WebEngineSearch(tab.AbstractSearch):

    ## TODO

    pass


class WebEngineCaret(tab.AbstractCaret):

    ## TODO

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_entered(self, mode):
        ## TODO
        pass

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode):
        ## TODO
        pass

    def has_selection(self):
        return self._widget.hasSelection()

    def selection(self, html=False):
        if html:
            raise NotImplementedError
        return self._widget.selectedText()


class WebEngineScroller(tab.AbstractScroller):

    def _key_press(self, key, count=1, getter_name=None, direction=None):
        # FIXME for some reason this does not work? :-/
        # FIXME Abort scrolling if the minimum/maximum was reached.
        press_evt = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, 0, 0, 0)
        release_evt = QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier, 0, 0, 0)
        self._widget.setFocus()
        for _ in range(count):
            QApplication.postEvent(self._widget, press_evt)
            QApplication.postEvent(self._widget, release_evt)

    def pos_perc(self):
        page = self._widget.page()
        try:
            size = page.contentsSize()
            pos = page.scrollPosition()
        except AttributeError:
            # Added in Qt 5.7
            return (None, None)
        else:
            # FIXME is this correct?
            perc_x = 100 / size.width() * pos.x()
            perc_y = 100 / size.height() * pos.y()
            return (perc_x, perc_y)

    def up(self, count=1):
        self._key_press(Qt.Key_Up, count, 'scrollBarMinimum', Qt.Vertical)

    def down(self, count=1):
        self._key_press(Qt.Key_Down, count, 'scrollBarMaximum', Qt.Vertical)

    def left(self, count=1):
        self._key_press(Qt.Key_Left, count, 'scrollBarMinimum', Qt.Horizontal)

    def right(self, count=1):
        self._key_press(Qt.Key_Right, count, 'scrollBarMaximum', Qt.Horizontal)

    def top(self):
        self._key_press(Qt.Key_Home)

    def bottom(self):
        self._key_press(Qt.Key_End)

    def page_up(self, count=1):
        self._key_press(Qt.Key_PageUp, count, 'scrollBarMinimum', Qt.Vertical)

    def page_down(self, count=1):
        self._key_press(Qt.Key_PageDown, count, 'scrollBarMaximum',
                        Qt.Vertical)

    ## TODO


class WebEngineHistory(tab.AbstractHistory):

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
        # TODO
        raise NotImplementedError


class WebEngineZoom(tab.AbstractZoom):

    def _set_factor_internal(self, factor):
        self._widget.setZoomFactor(factor)

    def factor(self):
        return self._widget.zoomFactor()


class WebEngineViewTab(tab.AbstractTab):

    def __init__(self, win_id, parent=None):
        super().__init__(win_id)
        widget = webview.WebEngineView()
        self.history = WebEngineHistory(self)
        self.scroll = WebEngineScroller()
        self.caret = WebEngineCaret(win_id=win_id, tab=self, parent=self)
        self.zoom = WebEngineZoom(win_id=win_id, parent=self)
        self.search = WebEngineSearch(parent=self)
        self._set_widget(widget)
        self._connect_signals()
        self.backend = tab.Backend.QtWebEngine

    def openurl(self, url):
        self._widget.load(url)

    @property
    def cur_url(self):
        return self._widget.url()

    @property
    def progress(self):
        return 0  # FIXME:refactor

    @property
    def load_status(self):
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
        # TODO
        pass

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

    def run_webaction(self, action):
        self._widget.triggerPageAction(action)

    def set_html(self, html, base_url):
        # FIXME check this and raise an exception if too big:
        # Warning: The content will be percent encoded before being sent to the
        # renderer via IPC. This may increase its size. The maximum size of the
        # percent encoded content is 2 megabytes minus 30 bytes.
        self._widget.setHtml(html, base_url)

    def _connect_signals(self):
        view = self._widget
        page = view.page()
        page.windowCloseRequested.connect(self.window_close_requested)
        page.linkHovered.connect(self.link_hovered)
        page.loadProgress.connect(self.load_progress)
        page.loadStarted.connect(self._on_load_started)
        view.titleChanged.connect(self.title_changed)
        page.loadFinished.connect(self.load_finished)
        # FIXME:refactor
        # view.iconChanged.connect(self.icon_changed)
        # view.scroll.pos_changed.connect(self.scroll.perc_changed)
        # view.url_text_changed.connect(self.url_text_changed)
        # view.load_status_changed.connect(self.load_status_changed)
