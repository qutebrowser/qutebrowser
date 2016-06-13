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

from qutebrowser.browser.tab import AbstractTab
from qutebrowser.browser.webkit.webview import WebView


class WebViewTab(AbstractTab):

    def __init__(self, win_id, parent=None):
        widget = WebView(win_id)
        super().__init__(widget)
        self._connect_signals()

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

        # Make sure we emit an appropriate status when loading finished.
        # While Qt has a bool "ok" attribute for loadFinished, it always is True
        # when using error pages...
        # See https://github.com/The-Compiler/qutebrowser/issues/84
        frame.loadFinished.connect(lambda:
                                  self.load_finished.emit(
                                      not self._widget.page().error_occured))

        # Emit iconChanged with a QIcon like QWebEngineView does.
        view.iconChanged.connect(lambda:
                                 self.icon_changed.emit(self._widget.icon()))
