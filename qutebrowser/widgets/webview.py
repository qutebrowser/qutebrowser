# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QTimer
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebView, QWebPage

import qutebrowser.config.config as config
import qutebrowser.keyinput.modeman as modeman
import qutebrowser.utils.message as message
import qutebrowser.utils.webelem as webelem
import qutebrowser.utils.log as log
from qutebrowser.utils.misc import elide
from qutebrowser.utils.qt import qt_ensure_valid
from qutebrowser.browser.webpage import BrowserPage
from qutebrowser.browser.hints import HintManager
from qutebrowser.utils.usertypes import (NeighborList, ClickTarget, KeyMode,
                                         enum)
from qutebrowser.commands.exceptions import CommandError


LoadStatus = enum('LoadStatus', 'none', 'success', 'error', 'warn', 'loading')


class WebView(QWebView):

    """One browser tab in TabbedBrowser.

    Our own subclass of a QWebView with some added bells and whistles.

    Attributes:
        hintmanager: The HintManager instance for this view.
        tabbedbrowser: The TabbedBrowser this WebView is part of.
                       We need this rather than signals to make createWindow
                       work.
        progress: loading progress of this page.
        scroll_pos: The current scroll position as (x%, y%) tuple.
        statusbar_message: The current javscript statusbar message.
        inspector: The QWebInspector used for this webview.
        open_target: Where to open the next tab ("normal", "tab", "tab_bg")
        _page: The QWebPage behind the view
        _url_text: The current URL as string.
                   Accessed via url_text property.
        _load_status: loading status of this page (index into LoadStatus)
                      Accessed via load_status property.
        _has_ssl_errors: Whether SSL errors occured during loading.
        _zoom: A NeighborList with the zoom levels.
        _old_scroll_pos: The old scroll position.
        _force_open_target: Override for _open_target.
        _check_insertmode: If True, in mouseReleaseEvent we should check if we
                           need to enter/leave insert mode.

    Signals:
        scroll_pos_changed: Scroll percentage of current tab changed.
                            arg 1: x-position in %.
                            arg 2: y-position in %.
        linkHovered: QWebPages linkHovered signal exposed.
        load_status_changed: The loading status changed
        url_text_changed: Current URL string changed.
    """

    scroll_pos_changed = pyqtSignal(int, int)
    linkHovered = pyqtSignal(str, str, str)
    load_status_changed = pyqtSignal(str)
    url_text_changed = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self._load_status = None
        self.load_status = LoadStatus.none
        self._check_insertmode = False
        self.tabbedbrowser = parent
        self.inspector = None
        self.scroll_pos = (-1, -1)
        self.statusbar_message = ''
        self._old_scroll_pos = (-1, -1)
        self._open_target = None
        self.open_target = ClickTarget.normal
        self._force_open_target = None
        self._zoom = None
        self._has_ssl_errors = False
        self._init_neighborlist()
        self._url_text = ''
        self.progress = 0
        self._page = BrowserPage(self)
        self.setPage(self._page)
        self.hintmanager = HintManager(self)
        self.hintmanager.mouse_event.connect(self.on_mouse_event)
        self.hintmanager.set_open_target.connect(self.set_force_open_target)
        self._page.linkHovered.connect(self.linkHovered)
        self._page.mainFrame().loadStarted.connect(self.on_load_started)
        self._page.change_title.connect(self.titleChanged)
        self.urlChanged.connect(self.on_url_changed)
        self._page.mainFrame().loadFinished.connect(self.on_load_finished)
        self.loadProgress.connect(lambda p: setattr(self, 'progress', p))
        self.page().statusBarMessage.connect(
            lambda msg: setattr(self, 'statusbar_message', msg))
        self.page().networkAccessManager().sslErrors.connect(
            lambda *args: setattr(self, '_has_ssl_errors', True))
        # FIXME find some way to hide scrollbars without setScrollBarPolicy

    def __repr__(self):
        url = self.url().toDisplayString()
        return "WebView(url='{}')".format(elide(url, 50))

    @property
    def open_target(self):
        """Getter for open_target so we can define a setter."""
        return self._open_target

    @open_target.setter
    def open_target(self, val):
        """Setter for open_target to do type checking."""
        if not isinstance(val, ClickTarget):
            raise TypeError("Target {} is no ClickTarget member!".format(val))
        self._open_target = val

    @property
    def load_status(self):
        """Getter for load_status."""
        return self._load_status

    @load_status.setter
    def load_status(self, val):
        """Setter for load_status.

        Emit:
            load_status_changed
        """
        if not isinstance(val, LoadStatus):
            raise TypeError("Type {} is no LoadStatus member!".format(val))
        log.webview.debug("load status for {}: {}".format(repr(self), val))
        self._load_status = val
        self.load_status_changed.emit(val.name)

    @property
    def url_text(self):
        """Getter for url_text."""
        return self._url_text

    @url_text.setter
    def url_text(self, val):
        """Setter for url_text.

        Emit:
            url_text_changed
        """
        self._url_text = val
        self.url_text_changed.emit(val)

    def _init_neighborlist(self):
        """Initialize the _zoom neighborlist."""
        self._zoom = NeighborList(config.get('ui', 'zoom-levels'),
                                  default=config.get('ui', 'default-zoom'),
                                  mode=NeighborList.Modes.block)

    def _mousepress_backforward(self, e):
        """Handle back/forward mouse button presses.

        Args:
            e: The QMouseEvent.
        """
        if e.button() == Qt.XButton1:
            # Back button on mice which have it.
            try:
                self.go_back()
            except CommandError as ex:
                message.error(ex, immediately=True)
        elif e.button() == Qt.XButton2:
            # Forward button on mice which have it.
            try:
                self.go_forward()
            except CommandError as ex:
                message.error(ex, immediately=True)

    def _mousepress_insertmode(self, e):
        """Switch to insert mode when an editable element was clicked.

        Args:
            e: The QMouseEvent.
        """
        pos = e.pos()
        frame = self.page().frameAt(pos)
        if frame is None:
            # This happens when we click inside the webview, but not actually
            # on the QWebPage - for example when clicking the scrollbar
            # sometimes.
            log.mouse.debug("Clicked at {} but frame is None!".format(pos))
            return
        # You'd think we have to subtract frame.geometry().topLeft() from the
        # position, but it seems QWebFrame::hitTestContent wants a position
        # relative to the QWebView, not to the frame. This makes no sense to
        # me, but it works this way.
        hitresult = frame.hitTestContent(pos)
        if hitresult.isNull():
            log.mouse.debug("Hitresult is null!")
        elem = hitresult.element()
        if elem.isNull():
            # For some reason, the hitresult element can be a null element
            # sometimes (e.g. when clicking the timetable fields on
            # http://www.sbb.ch/ ). If this is the case, we schedule a check
            # later (in mouseReleaseEvent) which uses webelem.focus_elem.
            log.mouse.debug("Hitresult element is null!")
            self._check_insertmode = True
            return
        elif ((hitresult.isContentEditable() and webelem.is_writable(elem)) or
                webelem.is_editable(elem)):
            log.mouse.debug("Clicked editable element!")
            modeman.enter(KeyMode.insert, 'click')
        else:
            log.mouse.debug("Clicked non-editable element!")
            if config.get('input', 'auto-leave-insert-mode'):
                modeman.maybe_leave(KeyMode.insert, 'click')

    def mouserelease_insertmode(self):
        """If we have an insertmode check scheduled, handle it."""
        if not self._check_insertmode:
            return
        self._check_insertmode = False
        elem = webelem.focus_elem(self.page().currentFrame())
        if webelem.is_editable(elem):
            log.mouse.debug("Clicked editable element (delayed)!")
            modeman.enter(KeyMode.insert, 'click-delayed')
        else:
            log.mouse.debug("Clicked non-editable element (delayed)!")
            if config.get('input', 'auto-leave-insert-mode'):
                modeman.maybe_leave(KeyMode.insert, 'click-delayed')

    def _mousepress_opentarget(self, e):
        """Set the open target when something was clicked.

        Args:
            e: The QMouseEvent.
        """
        if self._force_open_target is not None:
            self.open_target = self._force_open_target
            self._force_open_target = None
            log.mouse.debug("Setting force target: {}".format(
                self.open_target))
        elif (e.button() == Qt.MidButton or
              e.modifiers() & Qt.ControlModifier):
            if config.get('general', 'background-tabs'):
                self.open_target = ClickTarget.tab_bg
            else:
                self.open_target = ClickTarget.tab
            log.mouse.debug("Middle click, setting target: {}".format(
                self.open_target))
        else:
            self.open_target = ClickTarget.normal
            log.mouse.debug("Normal click, setting normal target")

    def shutdown(self):
        """Shut down the webview."""
        # We disable javascript because that prevents some segfaults when
        # quitting it seems.
        settings = self.settings()
        settings.setAttribute(QWebSettings.JavascriptEnabled, False)
        self.stop()
        nam = self.page().networkAccessManager()
        # Explicitely releasing the page here seems to prevent some segfaults
        # when quitting.
        # Copied from:
        # https://code.google.com/p/webscraping/source/browse/webkit.py#325
        self.setPage(None)
        nam.shutdown()
        del nam

    def openurl(self, url):
        """Open a URL in the browser.

        Args:
            url: The URL to load as QUrl

        Return:
            Return status of self.load

        Emit:
            titleChanged
        """
        qt_ensure_valid(url)
        urlstr = url.toDisplayString()
        log.webview.debug("New title: {}".format(urlstr))
        self.titleChanged.emit(urlstr)
        self.url_text = urlstr
        return self.load(url)

    def zoom_perc(self, perc, fuzzyval=True):
        """Zoom to a given zoom percentage.

        Args:
            perc: The zoom percentage as int.
            fuzzyval: Whether to set the NeighborLists fuzzyval.
        """
        if fuzzyval:
            self._zoom.fuzzyval = int(perc)
        if perc < 0:
            raise CommandError("Can't zoom {}%!".format(perc))
        self.setZoomFactor(float(perc) / 100)
        message.info("Zoom level: {}%".format(perc))

    def zoom(self, offset):
        """Increase/Decrease the zoom level.

        Args:
            offset: The offset in the zoom level list.
        """
        level = self._zoom.getitem(offset)
        self.zoom_perc(level, fuzzyval=False)

    @pyqtSlot(str, int)
    def search(self, text, flags):
        """Search for text in the current page.

        Args:
            text: The text to search for.
            flags: The QWebPage::FindFlags.
        """
        self._tabs.currentWidget().findText(text, flags)

    def go_back(self):
        """Go back a page in the history."""
        if self.page().history().canGoBack():
            self.back()
        else:
            raise CommandError("At beginning of history.")

    def go_forward(self):
        """Go forward a page in the history."""
        if self.page().history().canGoForward():
            self.forward()
        else:
            raise CommandError("At end of history.")

    @pyqtSlot('QUrl')
    def on_url_changed(self, url):
        """Update url_text when URL has changed."""
        qt_ensure_valid(url)
        self.url_text = url.toDisplayString()

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update tab config when config was changed."""
        if section == 'ui' and option in ('zoom-levels', 'default-zoom'):
            self._init_neighborlist()

    @pyqtSlot('QMouseEvent')
    def on_mouse_event(self, evt):
        """Post a new mouseevent from a hintmanager."""
        self.setFocus()
        QApplication.postEvent(self, evt)

    @pyqtSlot()
    def on_load_started(self):
        """Leave insert/hint mode and set vars when a new page is loading."""
        self.progress = 0
        self._has_ssl_errors = False
        self.load_status = LoadStatus.loading

    @pyqtSlot(bool)
    def on_load_finished(self, ok):
        """Handle auto-insert-mode after loading finished."""
        if ok and not self._has_ssl_errors:
            self.load_status = LoadStatus.success
        elif ok:
            self.load_status = LoadStatus.warn
        else:
            self.load_status = LoadStatus.error
        if not config.get('input', 'auto-insert-mode'):
            return
        if modeman.instance().mode == KeyMode.insert or not ok:
            return
        frame = self.page().currentFrame()
        elem = frame.findFirstElement(':focus')
        log.modes.debug("focus element: {}".format(elem.toOuterXml()))
        if elem.isNull():
            log.webview.debug("Focused element is null!")
        elif webelem.is_editable(elem):
            modeman.enter(KeyMode.insert, 'load finished')

    @pyqtSlot(str)
    def set_force_open_target(self, target):
        """Change the forced link target. Setter for _force_open_target.

        Args:
            target: A string to set self._force_open_target to.
        """
        t = getattr(ClickTarget, target)
        log.webview.debug("Setting force target to {}/{}".format(target, t))
        self._force_open_target = t

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
        if wintype == QWebPage.WebModalDialog:
            log.webview.warning("WebModalDialog requested, but we don't "
                                "support that!")
        if config.get('general', 'window-open-behaviour') == 'new-tab':
            return self.tabbedbrowser.tabopen()
        else:
            # FIXME for some odd reason, the history of the tab gets killed
            # here...
            return self

    def paintEvent(self, e):
        """Extend paintEvent to emit a signal if the scroll position changed.

        This is a bit of a hack: We listen to repaint requests here, in the
        hope a repaint will always be requested when scrolling, and if the
        scroll position actually changed, we emit a signal.

        Args:
            e: The QPaintEvent.

        Emit:
            scroll_pos_changed; If the scroll position changed.

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

    def mousePressEvent(self, e):
        """Extend QWidget::mousePressEvent().

        This does the following things:
            - Check if a link was clicked with the middle button or Ctrl and
              set the _open_target attribute accordingly.
            - Emit the editable_elem_selected signal if an editable element was
              clicked.

        Args:
            e: The arrived event.

        Return:
            The superclass return value.
        """
        if e.button() in (Qt.XButton1, Qt.XButton2):
            self._mousepress_backforward(e)
            super().mousePressEvent(e)
            return
        self._mousepress_insertmode(e)
        self._mousepress_opentarget(e)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        """Extend mouseReleaseEvent to enter insert mode if needed."""
        super().mouseReleaseEvent(e)
        # We want to make sure we check the focus element after the WebView is
        # updated completely.
        QTimer.singleShot(0, self.mouserelease_insertmode)
