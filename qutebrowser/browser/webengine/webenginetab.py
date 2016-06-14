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

from PyQt5.QtCore import pyqtSlot

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None

from qutebrowser.browser import tab
from qutebrowser.utils import usertypes, qtutils


class WebEngineHistory(tab.AbstractHistory):

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
        # TODO
        raise NotImplementedError


class WebEngineViewTab(tab.AbstractTab):

    def __init__(self, win_id, parent=None):
        super().__init__()
        widget = QWebEngineView()
        self.history = WebEngineHistory(self)
        self._set_widget(widget)
        self._connect_signals()

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

    @property
    def scroll_pos(self):
        return (0, 0)

    def _connect_signals(self):
        view = self._widget
        page = view.page()
        page.windowCloseRequested.connect(self.window_close_requested)
        page.linkHovered.connect(self.link_hovered)
        page.loadProgress.connect(self.load_progress)
        page.loadStarted.connect(self.load_started)
        view.titleChanged.connect(self.title_changed)
        page.loadFinished.connect(self.load_finished)
        # FIXME:refactor
        # view.iconChanged.connect(self.icon_changed)
        # view.scroll_pos_changed.connect(self.scroll_pos_changed)
        # view.url_text_changed.connect(self.url_text_changed)
        # view.load_status_changed.connect(self.load_status_changed)
