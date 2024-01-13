# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Customized QWebInspector for QtWebKit."""

# pylint: disable=no-name-in-module
from qutebrowser.qt.webkit import QWebSettings
from qutebrowser.qt.webkitwidgets import QWebInspector, QWebPage
# pylint: enable=no-name-in-module
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
