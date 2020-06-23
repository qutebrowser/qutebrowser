# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import typing
import pathlib

from PyQt5.QtCore import QUrl, QLibraryInfo
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWidgets import QWidget

from qutebrowser.browser import inspector
from qutebrowser.browser.webengine import webenginesettings
from qutebrowser.misc import miscwidgets
from qutebrowser.utils import version, qtutils


class WebEngineInspectorView(QWebEngineView):

    """The QWebEngineView used for the inspector.

    We don't use a qutebrowser WebEngineView because that has various
    customization which doesn't apply to the inspector.
    """

    def createWindow(self,
                     wintype: QWebEnginePage.WebWindowType) -> QWebEngineView:
        """Called by Qt when a page wants to create a new tab or window.

        In case the user wants to open a resource in a new tab, we use the
        createWindow handling of the main page to achieve that.

        See WebEngineView.createWindow for details.
        """
        return self.page().inspectedPage().view().createWindow(wintype)


def supports_new() -> bool:
    """Check whether a new-style inspector is supported."""
    return hasattr(QWebEnginePage, 'setInspectedPage')


class LegacyWebEngineInspector(inspector.AbstractWebInspector):

    """A web inspector for QtWebEngine without Qt API support.

    Only needed with Qt <= 5.10.
    """

    def __init__(self, splitter: miscwidgets.InspectorSplitter,
                 win_id: int,
                 parent: QWidget = None) -> None:
        super().__init__(splitter, win_id, parent)
        self._ensure_enabled()
        view = WebEngineInspectorView()
        self._settings = webenginesettings.WebEngineSettings(view.settings())
        self._set_widget(view)

    def _ensure_enabled(self) -> None:
        if 'QTWEBENGINE_REMOTE_DEBUGGING' not in os.environ:
            raise inspector.Error(
                "QtWebEngine inspector is not enabled. See "
                "'qutebrowser --help' for details.")

    def inspect(self, page: QWebEnginePage) -> None:  # type: ignore[override]
        # We're lying about the URL here a bit, but this way, URL patterns for
        # Qt 5.11/5.12/5.13 also work in this case.
        self._settings.update_for_url(QUrl('chrome-devtools://devtools'))
        port = int(os.environ['QTWEBENGINE_REMOTE_DEBUGGING'])
        self._widget.load(QUrl('http://localhost:{}/'.format(port)))


class WebEngineInspector(inspector.AbstractWebInspector):

    """A web inspector for QtWebEngine with Qt API support.

    Available since Qt 5.11.
    """

    def __init__(self, splitter: miscwidgets.InspectorSplitter,
                 win_id: int,
                 parent: QWidget = None) -> None:
        super().__init__(splitter, win_id, parent)
        self._check_devtools_resources()
        view = WebEngineInspectorView()
        self._settings = webenginesettings.WebEngineSettings(view.settings())
        self._set_widget(view)

    def _check_devtools_resources(self) -> None:
        """Make sure that the devtools resources are available on Fedora.

        Fedora packages devtools resources into its own package. If it's not
        installed, we show a nice error instead of a blank inspector.
        """
        dist = version.distribution()
        if dist is None or dist.parsed != version.Distribution.fedora:
            return

        data_path = pathlib.Path(QLibraryInfo.location(QLibraryInfo.DataPath))
        pak = data_path / 'resources' / 'qtwebengine_devtools_resources.pak'
        if not pak.exists():
            raise inspector.Error("QtWebEngine devtools resources not found, "
                                  "please install the qt5-webengine-devtools "
                                  "Fedora package.")

    def inspect(self, page: QWebEnginePage) -> None:  # type: ignore[override]
        inspector_page = self._widget.page()
        inspector_page.setInspectedPage(page)
        self._settings.update_for_url(inspector_page.requestedUrl())

    def _needs_recreate(self) -> bool:
        """Recreate the inspector when detaching to a window.

        WORKAROUND for what's likely an unknown Qt bug.
        """
        return qtutils.version_check('5.12')
