# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""The main browser widget for QtWebEngine."""

from typing import List, Iterable

from PyQt5.QtCore import pyqtSignal, QUrl
from PyQt5.QtGui import QPalette
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

from qutebrowser.browser import shared
from qutebrowser.browser.webengine import webenginesettings, certificateerror
from qutebrowser.config import config
from qutebrowser.utils import log, debug, usertypes


_QB_FILESELECTION_MODES = {
    QWebEnginePage.FileSelectOpen: shared.FileSelectionMode.single_file,
    QWebEnginePage.FileSelectOpenMultiple: shared.FileSelectionMode.multiple_files,
    # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-91489
    #
    # QtWebEngine doesn't expose this value from its internal
    # FilePickerControllerPrivate::FileChooserMode enum (i.e. it's not included in
    # the public QWebEnginePage::FileSelectionMode enum).
    # However, QWebEnginePage::chooseFiles is still called with the matching value
    # (2) when a file input with "webkitdirectory" is used.
    QWebEnginePage.FileSelectionMode(2): shared.FileSelectionMode.folder,
}


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

    def render_widget(self):
        """Get the RenderWidgetHostViewQt for this view."""
        return self.focusProxy()

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

    def contextMenuEvent(self, ev):
        """Prevent context menus when rocker gestures are enabled."""
        if config.val.input.mouse.rocker_gestures:
            ev.ignore()
            return
        super().contextMenuEvent(ev)


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
        try:
            return shared.javascript_confirm(
                url, js_msg, abort_on=[self.loadStarted, self.shutting_down])
        except shared.CallSuper:
            return super().javaScriptConfirm(url, js_msg)

    def javaScriptPrompt(self, url, js_msg, default):
        """Override javaScriptPrompt to use qutebrowser prompts."""
        if self._is_shutting_down:
            return (False, "")
        try:
            return shared.javascript_prompt(
                url, js_msg, default, abort_on=[self.loadStarted, self.shutting_down])
        except shared.CallSuper:
            return super().javaScriptPrompt(url, js_msg, default)

    def javaScriptAlert(self, url, js_msg):
        """Override javaScriptAlert to use qutebrowser prompts."""
        if self._is_shutting_down:
            return
        try:
            shared.javascript_alert(
                url, js_msg, abort_on=[self.loadStarted, self.shutting_down])
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

    def chooseFiles(
        self,
        mode: QWebEnginePage.FileSelectionMode,
        old_files: Iterable[str],
        accepted_mimetypes: Iterable[str],
    ) -> List[str]:
        """Override chooseFiles to (optionally) invoke custom file uploader."""
        handler = config.val.fileselect.handler
        if handler == "default":
            return super().chooseFiles(mode, old_files, accepted_mimetypes)
        assert handler == "external", handler
        try:
            qb_mode = _QB_FILESELECTION_MODES[mode]
        except KeyError:
            log.webview.warning(
                f"Got file selection mode {mode}, but we don't support that!"
            )
            return super().chooseFiles(mode, old_files, accepted_mimetypes)

        return shared.choose_file(qb_mode=qb_mode)
