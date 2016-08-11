# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""The main browser widget for QtWebEngine."""


from PyQt5.QtCore import pyqtSignal, QUrl
# pylint: disable=no-name-in-module,import-error,useless-suppression
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.config import config
from qutebrowser.utils import log, debug, usertypes


class WebEngineView(QWebEngineView):

    """Custom QWebEngineView subclass with qutebrowser-specific features."""

    def __init__(self, tabdata, parent=None):
        super().__init__(parent)
        self.setPage(WebEnginePage(tabdata, parent=self))


class WebEnginePage(QWebEnginePage):

    """Custom QWebEnginePage subclass with qutebrowser-specific features.

    Signals:
        certificate_error: FIXME:qtwebengine
        link_clicked: Emitted when a link was clicked on a page.
    """

    certificate_error = pyqtSignal()
    link_clicked = pyqtSignal(QUrl)

    def __init__(self, tabdata, parent=None):
        super().__init__(parent)
        self._tabdata = tabdata

    def certificateError(self, error):
        self.certificate_error.emit()
        return super().certificateError(error)

    def javaScriptConsoleMessage(self, level, msg, line, source):
        """Log javascript messages to qutebrowser's log."""
        # FIXME:qtwebengine maybe unify this in the tab api somehow?
        setting = config.get('general', 'log-javascript-console')
        if setting == 'none':
            return

        level_to_logger = {
            QWebEnginePage.InfoMessageLevel: log.js.info,
            QWebEnginePage.WarningMessageLevel: log.js.warning,
            QWebEnginePage.ErrorMessageLevel: log.js.error,
        }
        logstring = "[{}:{}] {}".format(source, line, msg)
        logger = level_to_logger[level]
        logger(logstring)

    def createWindow(self, _typ):
        """Handle new windows via JS."""
        log.stub()
        return None

    def acceptNavigationRequest(self,
                                url: QUrl,
                                typ: QWebEnginePage.NavigationType,
                                is_main_frame: bool):
        """Override acceptNavigationRequest to handle clicked links.

        Setting linkDelegationPolicy to DelegateAllLinks and using a slot bound
        to linkClicked won't work correctly, because when in a frameset, we
        have no idea in which frame the link should be opened.

        Checks if it should open it in a tab (middle-click or control) or not,
        and then conditionally opens the URL. Opening it in a new tab/window
        is handled in the slot connected to link_clicked.
        """
        target = self._tabdata.combined_target()
        log.webview.debug("navigation request: url {}, type {}, "
                          "target {}, is_main_frame {}".format(
                              url.toDisplayString(),
                              debug.qenum_key(QWebEnginePage, typ),
                              target, is_main_frame))

        if typ != QWebEnginePage.NavigationTypeLinkClicked:
            return True

        self.link_clicked.emit(url)

        return url.isValid() and target == usertypes.ClickTarget.normal
