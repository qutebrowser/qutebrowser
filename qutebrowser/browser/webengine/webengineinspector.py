# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# pylint: disable=no-name-in-module,import-error,useless-suppression
from PyQt5.QtWebEngineWidgets import QWebEngineView
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.browser import inspector


class WebEngineInspector(inspector.AbstractWebInspector):

    """A web inspector for QtWebEngine."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.port = None
        view = QWebEngineView()
        self._set_widget(view)

    def inspect(self, _page):
        """Set up the inspector."""
        try:
            port = int(os.environ['QTWEBENGINE_REMOTE_DEBUGGING'])
        except KeyError:
            raise inspector.WebInspectorError(
                "Debugging is not enabled. See 'qutebrowser --help' for "
                "details.")
        url = QUrl('http://localhost:{}/'.format(port))
        self._widget.load(url)
        self.show()
