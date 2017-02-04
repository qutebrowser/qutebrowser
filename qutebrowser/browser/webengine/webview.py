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
import functools

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QUrl, PYQT_VERSION
# pylint: disable=no-name-in-module,import-error,useless-suppression
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
# pylint: enable=no-name-in-module,import-error,useless-suppression

from qutebrowser.browser import shared
from qutebrowser.browser.webengine import certificateerror
from qutebrowser.config import config
from qutebrowser.utils import (log, debug, usertypes, qtutils, jinja, urlutils,
                               message)


class WebEngineView(QWebEngineView):

    """Custom QWebEngineView subclass with qutebrowser-specific features."""

    def __init__(self, tabdata, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self._tabdata = tabdata
        self.setPage(WebEnginePage(parent=self))

    def shutdown(self):
        self.page().shutdown()

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
        background_tabs = config.get('tabs', 'background-tabs')

        log.webview.debug("createWindow with type {}, background_tabs "
                          "{}".format(debug_type, background_tabs))

        try:
            background_tab_wintype = QWebEnginePage.WebBrowserBackgroundTab
        except AttributeError:
            # This is unavailable with an older PyQt, but we still might get
            # this with a newer Qt...
            background_tab_wintype = 0x0003

        if wintype == QWebEnginePage.WebBrowserWindow:
            # Shift-Alt-Click
            target = usertypes.ClickTarget.window
        elif wintype == QWebEnginePage.WebDialog:
            log.webview.warning("{} requested, but we don't support "
                                "that!".format(debug_type))
            target = usertypes.ClickTarget.tab
        elif wintype == QWebEnginePage.WebBrowserTab:
            # Middle-click / Ctrl-Click with Shift
            # FIXME:qtwebengine this also affects target=_blank links...
            if background_tabs:
                target = usertypes.ClickTarget.tab
            else:
                target = usertypes.ClickTarget.tab_bg
        elif wintype == background_tab_wintype:
            # Middle-click / Ctrl-Click
            if background_tabs:
                target = usertypes.ClickTarget.tab_bg
            else:
                target = usertypes.ClickTarget.tab
        else:
            raise ValueError("Invalid wintype {}".format(debug_type))

        tab = shared.get_tab(self._win_id, target)

        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-54419
        vercheck = qtutils.version_check
        qtbug54419_fixed = ((vercheck('5.6.2') and not vercheck('5.7.0')) or
                            qtutils.version_check('5.7.1') or
                            os.environ.get('QUTE_QTBUG54419_PATCHED', ''))
        if not qtbug54419_fixed:
            tab.needs_qtbug54419_workaround = True

        return tab._widget  # pylint: disable=protected-access


class WebEnginePage(QWebEnginePage):

    """Custom QWebEnginePage subclass with qutebrowser-specific features.

    Attributes:
        _is_shutting_down: Whether the page is currently shutting down.

    Signals:
        certificate_error: Emitted on certificate errors.
        shutting_down: Emitted when the page is shutting down.
    """

    certificate_error = pyqtSignal()
    shutting_down = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_shutting_down = False
        self.featurePermissionRequested.connect(
            self._on_feature_permission_requested)

    @pyqtSlot(QUrl, 'QWebEnginePage::Feature')
    def _on_feature_permission_requested(self, url, feature):
        """Ask the user for approval for geolocation/media/etc.."""
        options = {
            QWebEnginePage.Geolocation: ('content', 'geolocation'),
            QWebEnginePage.MediaAudioCapture: ('content', 'media-capture'),
            QWebEnginePage.MediaVideoCapture: ('content', 'media-capture'),
            QWebEnginePage.MediaAudioVideoCapture:
                ('content', 'media-capture'),
        }
        messages = {
            QWebEnginePage.Geolocation: 'access your location',
            QWebEnginePage.MediaAudioCapture: 'record audio',
            QWebEnginePage.MediaVideoCapture: 'record video',
            QWebEnginePage.MediaAudioVideoCapture: 'record audio/video',
        }
        assert options.keys() == messages.keys()

        if feature not in options:
            log.webview.error("Unhandled feature permission {}".format(
                debug.qenum_key(QWebEnginePage, feature)))
            self.setFeaturePermission(url, feature,
                                      QWebEnginePage.PermissionDeniedByUser)
            return

        yes_action = functools.partial(
            self.setFeaturePermission, url, feature,
            QWebEnginePage.PermissionGrantedByUser)
        no_action = functools.partial(
            self.setFeaturePermission, url, feature,
            QWebEnginePage.PermissionDeniedByUser)

        question = shared.feature_permission(
            url=url, option=options[feature], msg=messages[feature],
            yes_action=yes_action, no_action=no_action,
            abort_on=[self.shutting_down, self.loadStarted])

        if question is not None:
            self.featurePermissionRequestCanceled.connect(
                functools.partial(self._on_feature_permission_cancelled,
                                  question, url, feature))

    def _on_feature_permission_cancelled(self, question, url, feature,
                                         cancelled_url, cancelled_feature):
        """Slot invoked when a feature permission request was cancelled.

        To be used with functools.partial.
        """
        if url == cancelled_url and feature == cancelled_feature:
            try:
                question.abort()
            except RuntimeError:
                # The question could already be deleted, e.g. because it was
                # aborted after a loadStarted signal.
                pass

    def shutdown(self):
        self._is_shutting_down = True
        self.shutting_down.emit()

    def certificateError(self, error):
        """Handle certificate errors coming from Qt."""
        self.certificate_error.emit()
        url = error.url()
        error = certificateerror.CertificateErrorWrapper(error)
        log.webview.debug("Certificate error: {}".format(error))

        url_string = url.toDisplayString()
        error_page = jinja.render(
            'error.html', title="Error loading page: {}".format(url_string),
            url=url_string, error=str(error), icon='')

        if error.is_overridable():
            ignore = shared.ignore_certificate_errors(
                url, [error], abort_on=[self.loadStarted, self.shutting_down])
        else:
            log.webview.error("Non-overridable certificate error: "
                              "{}".format(error))
            ignore = False

        # We can't really know when to show an error page, as the error might
        # have happened when loading some resource.
        # However, self.url() is not available yet and self.requestedUrl()
        # might not match the URL we get from the error - so we just apply a
        # heuristic here.
        # See https://bugreports.qt.io/browse/QTBUG-56207
        log.webview.debug("ignore {}, URL {}, requested {}".format(
            ignore, url, self.requestedUrl()))
        if not ignore and url.matches(self.requestedUrl(), QUrl.RemoveScheme):
            self.setHtml(error_page)

        return ignore

    def javaScriptConfirm(self, url, js_msg):
        """Override javaScriptConfirm to use qutebrowser prompts."""
        if self._is_shutting_down:
            return False
        try:
            return shared.javascript_confirm(url, js_msg,
                                             abort_on=[self.loadStarted,
                                                       self.shutting_down])
        except shared.CallSuper:
            return super().javaScriptConfirm(url, js_msg)

    if PYQT_VERSION > 0x050700:
        # WORKAROUND
        # Can't override javaScriptPrompt with older PyQt versions
        # https://www.riverbankcomputing.com/pipermail/pyqt/2016-November/038293.html
        def javaScriptPrompt(self, url, js_msg, default):
            """Override javaScriptPrompt to use qutebrowser prompts."""
            if self._is_shutting_down:
                return (False, "")
            try:
                return shared.javascript_prompt(url, js_msg, default,
                                                abort_on=[self.loadStarted,
                                                          self.shutting_down])
            except shared.CallSuper:
                return super().javaScriptPrompt(url, js_msg, default)

    def javaScriptAlert(self, url, js_msg):
        """Override javaScriptAlert to use qutebrowser prompts."""
        if self._is_shutting_down:
            return
        try:
            shared.javascript_alert(url, js_msg,
                                    abort_on=[self.loadStarted,
                                              self.shutting_down])
        except shared.CallSuper:
            super().javaScriptAlert(url, js_msg)

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

        This only show an error on invalid links - everything else is handled
        in createWindow.
        """
        log.webview.debug("navigation request: url {}, type {}, is_main_frame "
                          "{}".format(url.toDisplayString(),
                                      debug.qenum_key(QWebEnginePage, typ),
                                      is_main_frame))
        if (typ == QWebEnginePage.NavigationTypeLinkClicked and
                not url.isValid()):
            msg = urlutils.get_errstring(url, "Invalid link clicked")
            message.error(msg)
            return False
        return True
