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

"""The main browser widgets."""

from PyQt5.QtCore import pyqtSignal, Qt, QUrl
from PyQt5.QtWidgets import QStyleFactory
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebView, QWebPage

from qutebrowser.config import config, stylesheet
from qutebrowser.keyinput import modeman
from qutebrowser.utils import log, usertypes, utils, objreg, debug
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

    STYLESHEET = """
        WebView {
            {% if conf.colors.webpage.bg %}
            background-color: {{ qcolor_to_qsscolor(conf.colors.webpage.bg) }};
            {% endif %}
        }
    """

    scroll_pos_changed = pyqtSignal(int, int)
    shutting_down = pyqtSignal()

    def __init__(self, *, win_id, tab_id, tab, private, parent=None):
        super().__init__(parent)
        if utils.is_mac:
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-42948
            # See https://github.com/qutebrowser/qutebrowser/issues/462
            self.setStyle(QStyleFactory.create('Fusion'))
        # FIXME:qtwebengine this is only used to set the zoom factor from
        # the QWebPage - we should get rid of it somehow (signals?)
        self.tab = tab
        self._tabdata = tab.data
        self.win_id = win_id
        self.scroll_pos = (-1, -1)
        self._old_scroll_pos = (-1, -1)
        self._tab_id = tab_id

        page = webpage.BrowserPage(win_id=self.win_id, tab_id=self._tab_id,
                                   tabdata=tab.data, private=private,
                                   parent=self)
        page.setVisibilityState(
            QWebPage.VisibilityStateVisible if self.isVisible()
            else QWebPage.VisibilityStateHidden)

        self.setPage(page)

        stylesheet.set_register(self)

    def __repr__(self):
        flags = QUrl.EncodeUnicode
        urlstr = self.url().toDisplayString(flags)  # type: ignore[arg-type]
        url = utils.elide(urlstr, 100)
        return utils.get_repr(self, tab_id=self._tab_id, url=url)

    def __del__(self):
        # Explicitly releasing the page here seems to prevent some segfaults
        # when quitting.
        # Copied from:
        # https://code.google.com/p/webscraping/source/browse/webkit.py#325
        try:
            self.setPage(None)  # type: ignore[arg-type]
        except RuntimeError:
            # It seems sometimes Qt has already deleted the QWebView and we
            # get: RuntimeError: wrapped C/C++ object of type WebView has been
            # deleted
            pass

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
        self.shutting_down.connect(menu.close)  # type: ignore[arg-type]
        mm = modeman.instance(self.win_id)
        mm.entered.connect(menu.close)  # type: ignore[arg-type]
        menu.exec_(e.globalPos())

    def showEvent(self, e):
        """Extend showEvent to set the page visibility state to visible.

        Args:
            e: The QShowEvent.

        Return:
            The superclass event return value.
        """
        super().showEvent(e)
        self.page().setVisibilityState(QWebPage.VisibilityStateVisible)

    def hideEvent(self, e):
        """Extend hideEvent to set the page visibility state to hidden.

        Args:
            e: The QHideEvent.

        Return:
            The superclass event return value.
        """
        super().hideEvent(e)
        self.page().setVisibilityState(QWebPage.VisibilityStateHidden)

    def mousePressEvent(self, e):
        """Set the tabdata ClickTarget on a mousepress.

        This is implemented here as we don't need it for QtWebEngine.
        """
        if e.button() == Qt.MidButton or e.modifiers() & Qt.ControlModifier:
            background = config.val.tabs.background
            if e.modifiers() & Qt.ShiftModifier:
                background = not background
            if background:
                target = usertypes.ClickTarget.tab_bg
            else:
                target = usertypes.ClickTarget.tab
            self._tabdata.open_target = target
            log.mouse.debug("Ctrl/Middle click, setting target: {}".format(
                target))
        else:
            self._tabdata.open_target = usertypes.ClickTarget.normal
            log.mouse.debug("Normal click, setting normal target")
        super().mousePressEvent(e)
