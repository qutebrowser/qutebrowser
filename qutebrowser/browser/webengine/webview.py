# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtCore import pyqtSignal, QUrl, PYQT_VERSION
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

from qutebrowser.browser import shared
from qutebrowser.browser.webengine import webenginesettings, certificateerror
from qutebrowser.config import config
from qutebrowser.utils import log, debug, usertypes, qtutils
from qutebrowser.misc import miscwidgets, objects
from qutebrowser.qt import sip


class WebEngineView(QWebEngineView):

    """Custom QWebEngineView subclass with qutebrowser-specific features."""

    def __init__(self, *, tabdata, win_id, private, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self._tabdata = tabdata

        theme_color = self.style().standardPalette().color(QPalette.Base)
        if private:
            assert webenginesettings.private_profile is not None
            profile = webenginesettings.private_profile
            assert profile.isOffTheRecord()
        else:
            profile = webenginesettings.default_profile
        page = WebEnginePage(theme_color=theme_color, profile=profile,
                             parent=self)
        self.setPage(page)

        if qtutils.version_check('5.11', compiled=False):
            # Set a PseudoLayout as a WORKAROUND for
            # https://bugreports.qt.io/browse/QTBUG-68224
            # and other related issues.
            sip.delete(self.layout())
            self._layout = miscwidgets.PseudoLayout(self)

    def render_widget(self):
        """Get the RenderWidgetHostViewQt for this view.

        Normally, this would always be the focusProxy().
        However, it sometimes isn't, so we use this as a WORKAROUND for
        https://bugreports.qt.io/browse/QTBUG-68727

        This got introduced in Qt 5.11.0 and fixed in 5.12.0.
        """
        if 'lost-focusproxy' not in objects.debug_flags:
            proxy = self.focusProxy()
            if proxy is not None:
                return proxy

        # We don't want e.g. a QMenu.
        rwhv_class = 'QtWebEngineCore::RenderWidgetHostViewQtDelegateWidget'
        children = [c for c in self.findChildren(QWidget)
                    if c.isVisible() and c.inherits(rwhv_class)]

        log.webview.debug("Found possibly lost focusProxy: {}"
                          .format(children))

        return children[-1] if children else None

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
                         WebEngineView.

        Return:
            The new QWebEngineView object.
        """
        debug_type = debug.qenum_key(QWebEnginePage, wintype)
        background = config.val.tabs.background

        log.webview.debug("createWindow with type {}, background {}".format(
            debug_type, background))

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
            if background:
                target = usertypes.ClickTarget.tab
            else:
                target = usertypes.ClickTarget.tab_bg
        elif wintype == QWebEnginePage.WebBrowserBackgroundTab:
            # Middle-click / Ctrl-Click
            if background:
                target = usertypes.ClickTarget.tab_bg
            else:
                target = usertypes.ClickTarget.tab
        else:
            raise ValueError("Invalid wintype {}".format(debug_type))

        tab = shared.get_tab(self._win_id, target)
        return tab._widget  # pylint: disable=protected-access


class WebEnginePage(QWebEnginePage):

    """Custom QWebEnginePage subclass with qutebrowser-specific features.

    Attributes:
        _is_shutting_down: Whether the page is currently shutting down.
        _theme_color: The theme background color.

    Signals:
        certificate_error: Emitted on certificate errors.
                           Needs to be directly connected to a slot setting the
                           'ignore' attribute.
        shutting_down: Emitted when the page is shutting down.
        navigation_request: Emitted on acceptNavigationRequest.
    """

    certificate_error = pyqtSignal(certificateerror.CertificateErrorWrapper)
    shutting_down = pyqtSignal()
    navigation_request = pyqtSignal(usertypes.NavigationRequest)

    def __init__(self, *, theme_color, profile, parent=None):
        super().__init__(profile, parent)
        self._is_shutting_down = False
        self._theme_color = theme_color
        self._set_bg_color()
        config.instance.changed.connect(self._set_bg_color)

    @config.change_filter('colors.webpage.bg')
    def _set_bg_color(self):
        col = config.val.colors.webpage.bg
        if col is None:
            col = self._theme_color
        self.setBackgroundColor(col)

    def shutdown(self):
        self._is_shutting_down = True
        self.shutting_down.emit()

    def certificateError(self, error):
        """Handle certificate errors coming from Qt."""
        error = certificateerror.CertificateErrorWrapper(error)
        self.certificate_error.emit(error)
        return error.ignore

    def javaScriptConfirm(self, url, js_msg):
        """Override javaScriptConfirm to use qutebrowser prompts."""
        if self._is_shutting_down:
            return False
        escape_msg = qtutils.version_check('5.11', compiled=False)
        try:
            return shared.javascript_confirm(url, js_msg,
                                             abort_on=[self.loadStarted,
                                                       self.shutting_down],
                                             escape_msg=escape_msg)
        except shared.CallSuper:
            return super().javaScriptConfirm(url, js_msg)

    if PYQT_VERSION > 0x050700:
        # WORKAROUND
        # Can't override javaScriptPrompt with older PyQt versions
        # https://www.riverbankcomputing.com/pipermail/pyqt/2016-November/038293.html
        def javaScriptPrompt(self, url, js_msg, default):
            """Override javaScriptPrompt to use qutebrowser prompts."""
            escape_msg = qtutils.version_check('5.11', compiled=False)
            if self._is_shutting_down:
                return (False, "")
            try:
                return shared.javascript_prompt(url, js_msg, default,
                                                abort_on=[self.loadStarted,
                                                          self.shutting_down],
                                                escape_msg=escape_msg)
            except shared.CallSuper:
                return super().javaScriptPrompt(url, js_msg, default)

    def javaScriptAlert(self, url, js_msg):
        """Override javaScriptAlert to use qutebrowser prompts."""
        if self._is_shutting_down:
            return
        escape_msg = qtutils.version_check('5.11', compiled=False)
        try:
            shared.javascript_alert(url, js_msg,
                                    abort_on=[self.loadStarted,
                                              self.shutting_down],
                                    escape_msg=escape_msg)
        except shared.CallSuper:
            super().javaScriptAlert(url, js_msg)

    def javaScriptConsoleMessage(self, level, msg, line, source):
        """Log javascript messages to qutebrowser's log."""
        level_map = {
            QWebEnginePage.InfoMessageLevel: usertypes.JsLogLevel.info,
            QWebEnginePage.WarningMessageLevel: usertypes.JsLogLevel.warning,
            QWebEnginePage.ErrorMessageLevel: usertypes.JsLogLevel.error,
        }
        shared.javascript_log_message(level_map[level], source, line, msg)

    def acceptNavigationRequest(self,
                                url: QUrl,
                                typ: QWebEnginePage.NavigationType,
                                is_main_frame: bool) -> bool:
        """Override acceptNavigationRequest to forward it to the tab API."""
        type_map = {
            QWebEnginePage.NavigationTypeLinkClicked:
                usertypes.NavigationRequest.Type.link_clicked,
            QWebEnginePage.NavigationTypeTyped:
                usertypes.NavigationRequest.Type.typed,
            QWebEnginePage.NavigationTypeFormSubmitted:
                usertypes.NavigationRequest.Type.form_submitted,
            QWebEnginePage.NavigationTypeBackForward:
                usertypes.NavigationRequest.Type.back_forward,
            QWebEnginePage.NavigationTypeReload:
                usertypes.NavigationRequest.Type.reloaded,
            QWebEnginePage.NavigationTypeOther:
                usertypes.NavigationRequest.Type.other,
        }
        try:
            type_map[QWebEnginePage.NavigationTypeRedirect] = (
                usertypes.NavigationRequest.Type.redirect)
        except AttributeError:
            # Added in Qt 5.14
            pass

        navigation = usertypes.NavigationRequest(
            url=url,
            navigation_type=type_map.get(
                typ, usertypes.NavigationRequest.Type.other),
            is_main_frame=is_main_frame)
        self.navigation_request.emit(navigation)
        return navigation.accepted
