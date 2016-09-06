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

import os

from PyQt5.QtCore import pyqtSignal, QUrl
# pylint: disable=no-name-in-module,import-error,useless-suppression
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.config import config
from qutebrowser.utils import log, debug, usertypes, objreg, qtutils


class WebEngineView(QWebEngineView):

    """Custom QWebEngineView subclass with qutebrowser-specific features."""

    def __init__(self, tabdata, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self.setPage(WebEnginePage(tabdata, parent=self))

    def createWindow(self, wintype):
        """Called by Qt when a page wants to create a new window.

        This function is called from the createWindow() method of the
        associated QWebEnginePage, each time the page wants to create a new
        window of the given type. This might be the result, for example, of a
        JavaScript request to open a document in a new window.

        Args:
            wintype: This enum describes the types of window that can be
                     created by the createWindow() function.

                     QWebEnginePage::WebBrowserWindow:
                         A complete web browser window.
                     QWebEnginePage::WebBrowserTab:
                         A web browser tab.
                     QWebEnginePage::WebDialog:
                         A window without decoration.
                     QWebEnginePage::WebBrowserBackgroundTab:
                         A web browser tab without hiding the current visible
                         WebEngineView. (Added in Qt 5.7)

        Return:
            The new QWebEngineView object.
        """
        debug_type = debug.qenum_key(QWebEnginePage, wintype)
        log.webview.debug("createWindow with type {}".format(debug_type))

        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-54419
        vercheck = qtutils.version_check
        qtbug_54419_fixed = ((vercheck('5.6.2') and not vercheck('5.7.0')) or
                             qtutils.version_check('5.7.1') or
                             os.environ.get('QUTE_QTBUG54419_PATCHED', ''))
        if not qtbug_54419_fixed:
            log.webview.debug("Ignoring createWindow because of QTBUG-54419")
            return None

        background = False
        if wintype in [QWebEnginePage.WebBrowserWindow,
                       QWebEnginePage.WebDialog]:
            log.webview.warning("{} requested, but we don't support "
                                "that!".format(debug_type))
        elif wintype == QWebEnginePage.WebBrowserTab:
            pass
        elif (hasattr(QWebEnginePage, 'WebBrowserBackgroundTab') and
              wintype == QWebEnginePage.WebBrowserBackgroundTab):
            background = True
        else:
            raise ValueError("Invalid wintype {}".format(debug_type))

        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)
        # pylint: disable=protected-access
        return tabbed_browser.tabopen(background=background)._widget


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
