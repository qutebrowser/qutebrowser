# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# FIXME:qt6 (lint)
# pylint: disable=no-name-in-module

"""Customized QWebInspector for QtWebKit."""

from qutebrowser.qt.webkit import QWebSettings
from qutebrowser.qt.webkitwidgets import QWebInspector, QWebPage
from qutebrowser.qt.widgets import QWidget

from qutebrowser.browser import inspector
from qutebrowser.misc import miscwidgets


class WebKitInspector(inspector.AbstractWebInspector):

    """A web inspector for QtWebKit."""

    def __init__(self, splitter: miscwidgets.InspectorSplitter,
                 win_id: int,
                 parent: QWidget = None) -> None:
        super().__init__(splitter, win_id, parent)
        qwebinspector = QWebInspector()
        self._set_widget(qwebinspector)

    def inspect(self, page: QWebPage) -> None:
        settings = QWebSettings.globalSettings()
        settings.setAttribute(QWebSettings.WebAttribute.DeveloperExtrasEnabled, True)
        self._widget.setPage(page)
