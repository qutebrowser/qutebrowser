# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import itertools
import functools

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QTimer, QUrl
from PyQt5.QtWidgets import QApplication, QStyleFactory
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebView, QWebPage

from qutebrowser.config import config
from qutebrowser.keyinput import modeman
from qutebrowser.utils import message, log, usertypes, utils, qtutils, objreg
from qutebrowser.browser import webpage, hints, webelem
from qutebrowser.commands import cmdexc


LoadStatus = usertypes.enum('LoadStatus', ['none', 'success', 'error', 'warn',
                                           'loading'])


tab_id_gen = itertools.count(0)


class WebView(QWebView):

    """One browser tab in TabbedBrowser.

    Our own subclass of a QWebView with some added bells and whistles.

    Attributes:
        hintmanager: The HintManager instance for this view.
        progress: loading progress of this page.
        scroll_pos: The current scroll position as (x%, y%) tuple.
        statusbar_message: The current javscript statusbar message.
        inspector: The QWebInspector used for this webview.
        load_status: loading status of this page (index into LoadStatus)
        open_target: Where to open the next tab ("normal", "tab", "tab_bg")
        viewing_source: Whether the webview is currently displaying source
                        code.
        registry: The ObjectRegistry associated with this tab.
        tab_id: The tab ID of the view.
        _cur_url: The current URL (accessed via cur_url property).
        _has_ssl_errors: Whether SSL errors occured during loading.
        _zoom: A NeighborList with the zoom levels.
        _old_scroll_pos: The old scroll position.
        _force_open_target: Override for open_target.
        _check_insertmode: If True, in mouseReleaseEvent we should check if we
                           need to enter/leave insert mode.
        _default_zoom_changed: Whether the zoom was changed from the default.
        _win_id: The window ID of the view.

    Signals:
        scroll_pos_changed: Scroll percentage of current tab changed.
                            arg 1: x-position in %.
                            arg 2: y-position in %.
        linkHovered: QWebPages linkHovered signal exposed.
        load_status_changed: The loading status changed
        url_text_changed: Current URL string changed.
        shutting_down: Emitted when the view is shutting down.
    """

    scroll_pos_changed = pyqtSignal(int, int)
    linkHovered = pyqtSignal(str, str, str)
    load_status_changed = pyqtSignal(str)
    url_text_changed = pyqtSignal(str)
    shutting_down = pyqtSignal()

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        if sys.platform == 'darwin' and qtutils.version_check('5.4'):
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-42948
            # See https://github.com/The-Compiler/qutebrowser/issues/462
            self.setStyle(QStyleFactory.create('Fusion'))
        self._win_id = win_id
        self.load_status = LoadStatus.none
        self._check_insertmode = False
        self.inspector = None
        self.scroll_pos = (-1, -1)
        self.statusbar_message = ''
        self._old_scroll_pos = (-1, -1)
        self.open_target = usertypes.ClickTarget.normal
        self._force_open_target = None
        self._zoom = None
        self._has_ssl_errors = False
        self.init_neighborlist()
        cfg = objreg.get('config')
        cfg.changed.connect(self.init_neighborlist)
        # For some reason, this signal doesn't get disconnected automatically
        # when the WebView is destroyed on older PyQt versions.
        # See https://github.com/The-Compiler/qutebrowser/issues/390
        self.destroyed.connect(functools.partial(
            cfg.changed.disconnect, self.init_neighborlist))
        self._cur_url = None
        self.cur_url = QUrl()
        self.progress = 0
        self.registry = objreg.ObjectRegistry()
        self.tab_id = next(tab_id_gen)
        tab_registry = objreg.get('tab-registry', scope='window',
                                  window=win_id)
        tab_registry[self.tab_id] = self
        objreg.register('webview', self, registry=self.registry)
        page = webpage.BrowserPage(win_id, self.tab_id, self)
        self.setPage(page)
        hintmanager = hints.HintManager(win_id, self.tab_id, self)
        hintmanager.mouse_event.connect(self.on_mouse_event)
        hintmanager.set_open_target.connect(self.set_force_open_target)
        objreg.register('hintmanager', hintmanager, registry=self.registry)
        mode_manager = objreg.get('mode-manager', scope='window',
                                  window=win_id)
        mode_manager.entered.connect(self.on_mode_entered)
        mode_manager.left.connect(self.on_mode_left)
        page.linkHovered.connect(self.linkHovered)
        page.mainFrame().loadStarted.connect(self.on_load_started)
        self.urlChanged.connect(self.on_url_changed)
        page.mainFrame().loadFinished.connect(self.on_load_finished)
        self.loadProgress.connect(lambda p: setattr(self, 'progress', p))
        self.page().statusBarMessage.connect(
            lambda msg: setattr(self, 'statusbar_message', msg))
        self.page().networkAccessManager().sslErrors.connect(
            lambda *args: setattr(self, '_has_ssl_errors', True))
        self.viewing_source = False
        self.setZoomFactor(float(config.get('ui', 'default-zoom')) / 100)
        self._default_zoom_changed = False
        objreg.get('config').changed.connect(self.on_config_changed)

    def __repr__(self):
        url = utils.elide(self.url().toDisplayString(), 50)
        return utils.get_repr(self, tab_id=self.tab_id, url=url)

    def __del__(self):
        # Explicitely releasing the page here seems to prevent some segfaults
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

    def _set_load_status(self, val):
        """Setter for load_status."""
        if not isinstance(val, LoadStatus):
            raise TypeError("Type {} is no LoadStatus member!".format(val))
        log.webview.debug("load status for {}: {}".format(repr(self), val))
        self.load_status = val
        self.load_status_changed.emit(val.name)

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Reinitialize the zoom neighborlist if related config changed."""
        if section == 'ui' and option in ('zoom-levels', 'default-zoom'):
            if not self._default_zoom_changed:
                self.setZoomFactor(float(config.get('ui', 'default-zoom')) /
                                   100)
            self._default_zoom_changed = False
            self.init_neighborlist()

    def init_neighborlist(self):
        """Initialize the _zoom neighborlist."""
        levels = config.get('ui', 'zoom-levels')
        self._zoom = usertypes.NeighborList(
            levels, mode=usertypes.NeighborList.Modes.block)
        self._zoom.fuzzyval = config.get('ui', 'default-zoom')

    def _mousepress_backforward(self, e):
        """Handle back/forward mouse button presses.

        Args:
            e: The QMouseEvent.
        """
        if e.button() == Qt.XButton1:
            # Back button on mice which have it.
            if self.page().history().canGoBack():
                self.back()
            else:
                message.error(self._win_id, "At beginning of history.",
                              immediately=True)
        elif e.button() == Qt.XButton2:
            # Forward button on mice which have it.
            if self.page().history().canGoForward():
                self.forward()
            else:
                message.error(self._win_id, "At end of history.",
                              immediately=True)

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
            # For some reason, the whole hitresult can be null sometimes (e.g.
            # on doodle menu links). If this is the case, we schedule a check
            # later (in mouseReleaseEvent) which uses webelem.focus_elem.
            log.mouse.debug("Hitresult is null!")
            self._check_insertmode = True
            return
        try:
            elem = webelem.WebElementWrapper(hitresult.element())
        except webelem.IsNullError:
            # For some reason, the hitresult element can be a null element
            # sometimes (e.g. when clicking the timetable fields on
            # http://www.sbb.ch/ ). If this is the case, we schedule a check
            # later (in mouseReleaseEvent) which uses webelem.focus_elem.
            log.mouse.debug("Hitresult element is null!")
            self._check_insertmode = True
            return
        if ((hitresult.isContentEditable() and elem.is_writable()) or
                elem.is_editable()):
            log.mouse.debug("Clicked editable element!")
            modeman.enter(self._win_id, usertypes.KeyMode.insert, 'click',
                          only_if_normal=True)
        else:
            log.mouse.debug("Clicked non-editable element!")
            if config.get('input', 'auto-leave-insert-mode'):
                modeman.maybe_leave(self._win_id, usertypes.KeyMode.insert,
                                    'click')

    def mouserelease_insertmode(self):
        """If we have an insertmode check scheduled, handle it."""
        if not self._check_insertmode:
            return
        self._check_insertmode = False
        try:
            elem = webelem.focus_elem(self.page().currentFrame())
        except webelem.IsNullError:
            log.mouse.warning("Element vanished!")
            return
        if elem.is_editable():
            log.mouse.debug("Clicked editable element (delayed)!")
            modeman.enter(self._win_id, usertypes.KeyMode.insert,
                          'click-delayed', only_if_normal=True)
        else:
            log.mouse.debug("Clicked non-editable element (delayed)!")
            if config.get('input', 'auto-leave-insert-mode'):
                modeman.maybe_leave(self._win_id, usertypes.KeyMode.insert,
                                    'click-delayed')

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
            background_tabs = config.get('tabs', 'background-tabs')
            if e.modifiers() & Qt.ShiftModifier:
                background_tabs = not background_tabs
            if background_tabs:
                self.open_target = usertypes.ClickTarget.tab_bg
            else:
                self.open_target = usertypes.ClickTarget.tab
            log.mouse.debug("Middle click, setting target: {}".format(
                self.open_target))
        else:
            self.open_target = usertypes.ClickTarget.normal
            log.mouse.debug("Normal click, setting normal target")

    def shutdown(self):
        """Shut down the webview."""
        self.shutting_down.emit()
        self.page().shutdown()
        # We disable javascript because that prevents some segfaults when
        # quitting it seems.
        log.destroy.debug("Shutting down {!r}.".format(self))
        settings = self.settings()
        settings.setAttribute(QWebSettings.JavascriptEnabled, False)
        self.stop()

    def openurl(self, url):
        """Open a URL in the browser.

        Args:
            url: The URL to load as QUrl
        """
        qtutils.ensure_valid(url)
        urlstr = url.toDisplayString()
        log.webview.debug("New title: {}".format(urlstr))
        self.titleChanged.emit(urlstr)
        self.cur_url = url
        self.url_text_changed.emit(url.toDisplayString())
        self.load(url)
        if url.scheme() == 'qute':
            frame = self.page().mainFrame()
            frame.javaScriptWindowObjectCleared.connect(self.add_js_bridge)

    def add_js_bridge(self):
        """Add the javascript bridge for qute:... pages."""
        frame = self.sender()
        if frame.url().scheme() == 'qute':
            bridge = objreg.get('js-bridge')
            frame.addToJavaScriptWindowObject('qute', bridge)

    def zoom_perc(self, perc, fuzzyval=True):
        """Zoom to a given zoom percentage.

        Args:
            perc: The zoom percentage as int.
            fuzzyval: Whether to set the NeighborLists fuzzyval.
        """
        if fuzzyval:
            self._zoom.fuzzyval = int(perc)
        if perc < 0:
            raise cmdexc.CommandError("Can't zoom {}%!".format(perc))
        self.setZoomFactor(float(perc) / 100)
        message.info(self._win_id, "Zoom level: {}%".format(perc))
        self._default_zoom_changed = True

    def zoom(self, offset):
        """Increase/Decrease the zoom level.

        Args:
            offset: The offset in the zoom level list.
        """
        level = self._zoom.getitem(offset)
        self.zoom_perc(level, fuzzyval=False)

    @pyqtSlot('QUrl')
    def on_url_changed(self, url):
        """Update cur_url when URL has changed.

        If the URL is invalid, we just ignore it here.
        """
        if url.isValid():
            self.cur_url = url
            self.url_text_changed.emit(url.toDisplayString())

    @pyqtSlot('QMouseEvent')
    def on_mouse_event(self, evt):
        """Post a new mouseevent from a hintmanager."""
        log.modes.debug("Hint triggered, focusing {!r}".format(self))
        self.setFocus()
        QApplication.postEvent(self, evt)

    @pyqtSlot()
    def on_load_started(self):
        """Leave insert/hint mode and set vars when a new page is loading."""
        self.progress = 0
        self.viewing_source = False
        self._has_ssl_errors = False
        self._set_load_status(LoadStatus.loading)

    @pyqtSlot()
    def on_load_finished(self):
        """Handle auto-insert-mode after loading finished.

        We don't take loadFinished's ok argument here as it always seems to be
        true when the QWebPage has an ErrorPageExtension implemented.
        See https://github.com/The-Compiler/qutebrowser/issues/84
        """
        ok = not self.page().error_occured
        if ok and not self._has_ssl_errors:
            self._set_load_status(LoadStatus.success)
        elif ok:
            self._set_load_status(LoadStatus.warn)
        else:
            self._set_load_status(LoadStatus.error)
        if not config.get('input', 'auto-insert-mode'):
            return
        mode_manager = objreg.get('mode-manager', scope='window',
                                  window=self._win_id)
        cur_mode = mode_manager.mode
        if cur_mode == usertypes.KeyMode.insert or not ok:
            return
        frame = self.page().currentFrame()
        try:
            elem = webelem.WebElementWrapper(frame.findFirstElement(':focus'))
        except webelem.IsNullError:
            log.webview.debug("Focused element is null!")
            return
        log.modes.debug("focus element: {}".format(repr(elem)))
        if elem.is_editable():
            modeman.enter(self._win_id, usertypes.KeyMode.insert,
                          'load finished', only_if_normal=True)

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_entered(self, mode):
        """Ignore attempts to focus the widget if in any status-input mode."""
        if mode in (usertypes.KeyMode.command, usertypes.KeyMode.prompt,
                    usertypes.KeyMode.yesno):
            log.webview.debug("Ignoring focus because mode {} was "
                              "entered.".format(mode))
            self.setFocusPolicy(Qt.NoFocus)

    @pyqtSlot(usertypes.KeyMode)
    def on_mode_left(self, mode):
        """Restore focus policy if status-input modes were left."""
        if mode in (usertypes.KeyMode.command, usertypes.KeyMode.prompt,
                    usertypes.KeyMode.yesno):
            log.webview.debug("Restoring focus policy because mode {} was "
                              "left.".format(mode))
        self.setFocusPolicy(Qt.WheelFocus)

    @pyqtSlot(str)
    def set_force_open_target(self, target):
        """Change the forced link target. Setter for _force_open_target.

        Args:
            target: A string to set self._force_open_target to.
        """
        t = getattr(usertypes.ClickTarget, target)
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
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)
        return tabbed_browser.tabopen(background=False)

    def paintEvent(self, e):
        """Extend paintEvent to emit a signal if the scroll position changed.

        This is a bit of a hack: We listen to repaint requests here, in the
        hope a repaint will always be requested when scrolling, and if the
        scroll position actually changed, we emit a signal.

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

    def mousePressEvent(self, e):
        """Extend QWidget::mousePressEvent().

        This does the following things:
            - Check if a link was clicked with the middle button or Ctrl and
              set the open_target attribute accordingly.
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

    def contextMenuEvent(self, e):
        """Save a reference to the context menu so we can close it."""
        menu = self.page().createStandardContextMenu()
        self.shutting_down.connect(menu.close)
        menu.exec_(e.globalPos())
