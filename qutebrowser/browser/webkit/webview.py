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

"""The main browser widgets."""

import sys

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QUrl
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QStyleFactory
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebView, QWebPage, QWebFrame

from qutebrowser.config import config
from qutebrowser.keyinput import modeman
from qutebrowser.utils import log, usertypes, utils, qtutils, objreg, debug
from qutebrowser.browser.webkit import webpage


class WebView(QWebView):

    """Custom QWebView subclass with qutebrowser-specific features.

    Attributes:
        tab: The WebKitTab object for this WebView
        hintmanager: The HintManager instance for this view.
        scroll_pos: The current scroll position as (x%, y%) tuple.
        win_id: The window ID of the view.
        _tab_id: The tab ID of the view.
        _old_scroll_pos: The old scroll position.

    Signals:
        scroll_pos_changed: Scroll percentage of current tab changed.
                            arg 1: x-position in %.
                            arg 2: y-position in %.
        shutting_down: Emitted when the view is shutting down.
    """

    scroll_pos_changed = pyqtSignal(int, int)
    shutting_down = pyqtSignal()

    def __init__(self, win_id, tab_id, tab, parent=None):
        super().__init__(parent)
        if sys.platform == 'darwin' and qtutils.version_check('5.4'):
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-42948
            # See https://github.com/The-Compiler/qutebrowser/issues/462
            self.setStyle(QStyleFactory.create('Fusion'))
        # FIXME:qtwebengine this is only used to set the zoom factor from
        # the QWebPage - we should get rid of it somehow (signals?)
        self.tab = tab
        self._tabdata = tab.data
        self.win_id = win_id
        self.scroll_pos = (-1, -1)
        self._old_scroll_pos = (-1, -1)
        self._set_bg_color()
        self._tab_id = tab_id

        page = webpage.BrowserPage(self.win_id, self._tab_id, tab.data,
                                   parent=self)

        try:
            page.setVisibilityState(
                QWebPage.VisibilityStateVisible if self.isVisible()
                else QWebPage.VisibilityStateHidden)
        except AttributeError:
            pass

        self.setPage(page)

        mode_manager = objreg.get('mode-manager', scope='window',
                                  window=win_id)
        mode_manager.entered.connect(self.on_mode_entered)
        mode_manager.left.connect(self.on_mode_left)
        objreg.get('config').changed.connect(self._set_bg_color)

    def __repr__(self):
        url = utils.elide(self.url().toDisplayString(QUrl.EncodeUnicode), 100)
        return utils.get_repr(self, tab_id=self._tab_id, url=url)

    def __del__(self):
        # Explicitly releasing the page here seems to prevent some segfaults
        # when quitting.
        # Copied from:
        # https://code.google.com/p/webscraping/source/browse/webkit.py#325
        try:
            self.setPage(None)
        except RuntimeError:
            # It seems sometimes Qt has already deleted the QWebView and we
            # get: RuntimeError: wrapped C/C++ object of type WebView has been
            # deleted
            pass

    @config.change_filter('colors', 'webpage.bg')
    def _set_bg_color(self):
        """Set the webpage background color as configured.

        FIXME:qtwebengine
        For QtWebEngine, doing the same has no effect, so we do it in here.
        """
        col = config.get('colors', 'webpage.bg')
        palette = self.palette()
        if col is None:
            col = self.style().standardPalette().color(QPalette.Base)
        palette.setColor(QPalette.Base, col)
        self.setPalette(palette)

    def shutdown(self):
        """Shut down the webview."""
        self.shutting_down.emit()
        # We disable javascript because that prevents some segfaults when
        # quitting it seems.
        log.destroy.debug("Shutting down {!r}.".format(self))
        settings = self.settings()
        settings.setAttribute(QWebSettings.JavascriptEnabled, False)
        self.stop()
        self.page().shutdown()

    def openurl(self, url):
        """Open a URL in the browser.

        Args:
            url: The URL to load as QUrl
        """
        self.load(url)
        if url.scheme() == 'qute':
            frame = self.page().mainFrame()
            frame.javaScriptWindowObjectCleared.connect(self.add_js_bridge)

    @pyqtSlot()
    def add_js_bridge(self):
        """Add the javascript bridge for qute:... pages."""
        frame = self.sender()
        if not isinstance(frame, QWebFrame):
            log.webview.error("Got non-QWebFrame {!r} in "
                              "add_js_bridge!".format(frame))
            return

        if frame.url().scheme() == 'qute':
            bridge = objreg.get('js-bridge')
            frame.addToJavaScriptWindowObject('qute', bridge)

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_entered(self, mode):
        """Ignore attempts to focus the widget if in any status-input mode.

        FIXME:qtwebengine
        For QtWebEngine, doing the same has no effect, so we do it in here.
        """
        if mode in [usertypes.KeyMode.command, usertypes.KeyMode.prompt,
                    usertypes.KeyMode.yesno]:
            log.webview.debug("Ignoring focus because mode {} was "
                              "entered.".format(mode))
            self.setFocusPolicy(Qt.NoFocus)

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode):
        """Restore focus policy if status-input modes were left.

        FIXME:qtwebengine
        For QtWebEngine, doing the same has no effect, so we do it in here.
        """
        if mode in [usertypes.KeyMode.command, usertypes.KeyMode.prompt,
                    usertypes.KeyMode.yesno]:
            log.webview.debug("Restoring focus policy because mode {} was "
                              "left.".format(mode))
        self.setFocusPolicy(Qt.WheelFocus)

    def createWindow(self, wintype):
        """Called by Qt when a page wants to create a new window.

        This function is called from the createWindow() method of the
        associated QWebPage, each time the page wants to create a new window of
        the given type. This might be the result, for example, of a JavaScript
        request to open a document in a new window.

        Args:
            wintype: This enum describes the types of window that can be
                     created by the createWindow() function.

                     QWebPage::WebBrowserWindow: The window is a regular web
                                                 browser window.
                     QWebPage::WebModalDialog: The window acts as modal dialog.

        Return:
            The new QWebView object.
        """
        debug_type = debug.qenum_key(QWebPage, wintype)
        log.webview.debug("createWindow with type {}".format(debug_type))
        if wintype == QWebPage.WebModalDialog:
            log.webview.warning("WebModalDialog requested, but we don't "
                                "support that!")
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self.win_id)
        # pylint: disable=protected-access
        return tabbed_browser.tabopen(background=False)._widget

    def paintEvent(self, e):
        """Extend paintEvent to emit a signal if the scroll position changed.

        This is a bit of a hack: We listen to repaint requests here, in the
        hope a repaint will always be requested when scrolling, and if the
        scroll position actually changed, we emit a signal.

        QtWebEngine has a scrollPositionChanged signal, so it's not needed
        there.

        Args:
            e: The QPaintEvent.

        Return:
            The superclass event return value.
        """
        frame = self.page().mainFrame()
        new_pos = (frame.scrollBarValue(Qt.Horizontal),
                   frame.scrollBarValue(Qt.Vertical))
        if self._old_scroll_pos != new_pos:
            self._old_scroll_pos = new_pos
            m = (frame.scrollBarMaximum(Qt.Horizontal),
                 frame.scrollBarMaximum(Qt.Vertical))
            perc = (round(100 * new_pos[0] / m[0]) if m[0] != 0 else 0,
                    round(100 * new_pos[1] / m[1]) if m[1] != 0 else 0)
            self.scroll_pos = perc
            self.scroll_pos_changed.emit(*perc)
        # Let superclass handle the event
        super().paintEvent(e)

    def contextMenuEvent(self, e):
        """Save a reference to the context menu so we can close it.

        This is not needed for QtWebEngine, so it's in here.
        """
        menu = self.page().createStandardContextMenu()
        self.shutting_down.connect(menu.close)
        modeman.instance(self.win_id).entered.connect(menu.close)
        menu.exec_(e.globalPos())

    def showEvent(self, e):
        """Extend showEvent to set the page visibility state to visible.

        Args:
            e: The QShowEvent.

        Return:
            The superclass event return value.
        """
        try:
            self.page().setVisibilityState(QWebPage.VisibilityStateVisible)
        except AttributeError:
            pass

        super().showEvent(e)

    def hideEvent(self, e):
        """Extend hideEvent to set the page visibility state to hidden.

        Args:
            e: The QHideEvent.

        Return:
            The superclass event return value.
        """
        try:
            self.page().setVisibilityState(QWebPage.VisibilityStateHidden)
        except AttributeError:
            pass

        super().hideEvent(e)

    def mousePressEvent(self, e):
        """Set the tabdata ClickTarget on a mousepress.

        This is implemented here as we don't need it for QtWebEngine.
        """
        if e.button() == Qt.MidButton or e.modifiers() & Qt.ControlModifier:
            background_tabs = config.get('tabs', 'background-tabs')
            if e.modifiers() & Qt.ShiftModifier:
                background_tabs = not background_tabs
            if background_tabs:
                target = usertypes.ClickTarget.tab_bg
            else:
                target = usertypes.ClickTarget.tab
            self.page().open_target = target
            log.mouse.debug("Ctrl/Middle click, setting target: {}".format(
                target))
        else:
            self.page().open_target = usertypes.ClickTarget.normal
            log.mouse.debug("Normal click, setting normal target")
        super().mousePressEvent(e)
