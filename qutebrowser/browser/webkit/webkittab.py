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

"""Wrapper over our (QtWebKit) WebView."""

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWebKitWidgets import QWebPage

from qutebrowser.browser import tab
from qutebrowser.browser.webkit import webview
from qutebrowser.utils import qtutils


class WebViewHistory(tab.AbstractHistory):

    def __iter__(self):
        return iter(self.history.items())

    def current_idx(self):
        return self.history.currentItemIndex()

    def back(self):
        self.history.back()

    def forward(self):
        self.history.forward()

    def can_go_back(self):
        return self.history.canGoBack()

    def can_go_forward(self):
        return self.history.canGoForward()

    def serialize(self):
        return qtutils.serialize(self.history)

    def deserialize(self, data):
        return qtutils.deserialize(self.history)

    def load_items(self, items):
        stream, _data, user_data = tabhistory.serialize(items)
        qtutils.deserialize_stream(stream, self.history)
        for i, data in enumerate(user_data):
            self.history.itemAt(i).setUserData(data)
        cur_data = self.history.currentItem().userData()
        if cur_data is not None:
            if 'zoom' in cur_data:
                self.tab.zoom_perc(cur_data['zoom'] * 100)
            if ('scroll-pos' in cur_data and
                    self.tab.scroll_position() == QPoint(0, 0)):
                QTimer.singleShot(0, functools.partial(
                    self.tab.scroll, cur_data['scroll-pos']))


class WebViewTab(tab.AbstractTab):

    def __init__(self, win_id, parent=None):
        super().__init__()
        widget = webview.WebView(win_id, self.tab_id)
        self.history = WebViewHistory(self)
        self._set_widget(widget)
        self._connect_signals()

    def openurl(self, url):
        self._widget.openurl(url)

    @property
    def cur_url(self):
        return self._widget.cur_url

    @property
    def progress(self):
        return self._widget.progress

    @property
    def load_status(self):
        return self._widget.load_status

    @property
    def scroll_pos(self):
        return self._widget.scroll_pos

    def dump_async(self, callback=None, *, plain=False):
        frame = self._widget.page().mainFrame()
        if plain:
            callback(frame.toPlainText())
        else:
            callback(frame.toHtml())

    def shutdown(self):
        self._widget.shutdown()

    def reload(self, *, force=False):
        if force:
            action = QWebPage.ReloadAndBypassCache
        else:
            action = QWebPage.Reload
        self._widget.triggerPageAction(action)

    def stop(self):
        self._widget.stop()

    def title(self):
        return self._widget.title()

    def set_zoom_factor(self, factor):
        self._widget.setZoomFactor(factor)

    def zoom_factor(self):
        return self._widget.zoomFactor()

    def _connect_signals(self):
        view = self._widget
        page = view.page()
        frame = page.mainFrame()
        page.windowCloseRequested.connect(self.window_close_requested)
        page.linkHovered.connect(self.link_hovered)
        page.loadProgress.connect(self.load_progress)
        frame.loadStarted.connect(self.load_started)
        view.scroll_pos_changed.connect(self.scroll_pos_changed)
        view.titleChanged.connect(self.title_changed)
        view.url_text_changed.connect(self.url_text_changed)
        view.load_status_changed.connect(self.load_status_changed)
        view.shutting_down.connect(self.shutting_down)

        # Make sure we emit an appropriate status when loading finished.
        # While Qt has a bool "ok" attribute for loadFinished, it always is True
        # when using error pages...
        # See https://github.com/The-Compiler/qutebrowser/issues/84
        frame.loadFinished.connect(lambda:
                                   self.load_finished.emit(
                                       not self._widget.page().error_occurred))

        # Emit iconChanged with a QIcon like QWebEngineView does.
        view.iconChanged.connect(lambda:
                                 self.icon_changed.emit(self._widget.icon()))
