# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Customized QWebInspector for QtWebEngine."""

import os

from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings

from qutebrowser.browser import inspector


class WebEngineInspector(inspector.AbstractWebInspector):

    """A web inspector for QtWebEngine."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.port = None
        view = QWebEngineView()
        settings = view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self._set_widget(view)

    def _inspect_old(self, page):
        """Set up the inspector for Qt < 5.11."""
        try:
            port = int(os.environ['QTWEBENGINE_REMOTE_DEBUGGING'])
        except KeyError:
            raise inspector.WebInspectorError(
                "QtWebEngine inspector is not enabled. See "
                "'qutebrowser --help' for details.")
        url = QUrl('http://localhost:{}/'.format(port))

        if page is None:
            self._widget.load(QUrl('about:blank'))
        else:
            self._widget.load(url)

    def _inspect_new(self, page):
        """Set up the inspector for Qt >= 5.11."""
        self._widget.page().setInspectedPage(page)

    def inspect(self, page):
        try:
            self._inspect_new(page)
        except AttributeError:
            self._inspect_old(page)
