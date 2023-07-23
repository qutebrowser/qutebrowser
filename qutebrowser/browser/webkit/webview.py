# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The main browser widgets."""

from qutebrowser.qt.core import pyqtSignal, Qt
# pylint: disable=no-name-in-module
from qutebrowser.qt.webkit import QWebSettings
from qutebrowser.qt.webkitwidgets import QWebView, QWebPage
# pylint: enable=no-name-in-module

from qutebrowser.config import config, stylesheet
from qutebrowser.keyinput import modeman
from qutebrowser.utils import log, usertypes, utils, objreg, debug, urlutils
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
            QWebPage.VisibilityState.VisibilityStateVisible if self.isVisible()
            else QWebPage.VisibilityState.VisibilityStateHidden)

        self.setPage(page)

        stylesheet.set_register(self)

    def __repr__(self):
        urlstr = self.url().toDisplayString(urlutils.FormatOption.ENCODE_UNICODE)
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
        settings.setAttribute(QWebSettings.WebAttribute.JavascriptEnabled, False)
        self.stop()
        page = self.page()
        assert isinstance(page, webpage.BrowserPage), page
        page.shutdown()

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
        if wintype == QWebPage.WebWindowType.WebModalDialog:
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
        """
        frame = self.page().mainFrame()
        new_pos = (frame.scrollBarValue(Qt.Orientation.Horizontal),
                   frame.scrollBarValue(Qt.Orientation.Vertical))
        if self._old_scroll_pos != new_pos:
            self._old_scroll_pos = new_pos
            m = (frame.scrollBarMaximum(Qt.Orientation.Horizontal),
                 frame.scrollBarMaximum(Qt.Orientation.Vertical))
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
        mm = modeman.instance(self.win_id)
        mm.entered.connect(menu.close)
        menu.exec(e.globalPos())

    def showEvent(self, e):
        """Extend showEvent to set the page visibility state to visible.

        Args:
            e: The QShowEvent.
        """
        super().showEvent(e)
        self.page().setVisibilityState(QWebPage.VisibilityState.VisibilityStateVisible)

    def hideEvent(self, e):
        """Extend hideEvent to set the page visibility state to hidden.

        Args:
            e: The QHideEvent.
        """
        super().hideEvent(e)
        self.page().setVisibilityState(QWebPage.VisibilityState.VisibilityStateHidden)

    def mousePressEvent(self, e):
        """Set the tabdata ClickTarget on a mousepress.

        This is implemented here as we don't need it for QtWebEngine.
        """
        if e.button() == Qt.MouseButton.MidButton or e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            background = config.val.tabs.background
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
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
