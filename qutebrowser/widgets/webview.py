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

import logging
import functools

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebView, QWebPage

import qutebrowser.utils.url as urlutils
import qutebrowser.config.config as config
import qutebrowser.keyinput.modeman as modeman
import qutebrowser.utils.message as message
import qutebrowser.utils.webelem as webelem
from qutebrowser.browser.webpage import BrowserPage
from qutebrowser.browser.hints import HintManager
from qutebrowser.utils.signals import SignalCache
from qutebrowser.utils.usertypes import NeighborList, enum


Target = enum('normal', 'tab', 'bgtab')


class WebView(QWebView):

    """One browser tab in TabbedBrowser.

    Our own subclass of a QWebView with some added bells and whistles.

    Attributes:
        page_: The QWebPage behind the view
        signal_cache: The signal cache associated with the view.
        hintmanager: The HintManager instance for this view.
        tabbedbrowser: The TabbedBrowser this WebView is part of.
                       We need this rather than signals to make createWindow
                       work.
        _zoom: A NeighborList with the zoom levels.
        _scroll_pos: The old scroll position.
        _shutdown_callback: Callback to be called after shutdown.
        _open_target: Where to open the next tab ("normal", "tab", "bgtab")
        _force_open_target: Override for _open_target.
        _shutdown_callback: The callback to call after shutting down.
        _destroyed: Dict of all items to be destroyed on shtudown.

    Signals:
        scroll_pos_changed: Scroll percentage of current tab changed.
                            arg 1: x-position in %.
                            arg 2: y-position in %.
        linkHovered: QWebPages linkHovered signal exposed.
    """

    scroll_pos_changed = pyqtSignal(int, int)
    linkHovered = pyqtSignal(str, str, str)

    def __init__(self, parent):
        super().__init__(parent)
        self.tabbedbrowser = parent
        self._scroll_pos = (-1, -1)
        self._shutdown_callback = None
        self._open_target = Target.normal
        self._force_open_target = None
        self._destroyed = {}
        self._zoom = None
        self._init_neighborlist()
        self.page_ = BrowserPage(self)
        self.setPage(self.page_)
        self.hintmanager = HintManager(self)
        self.hintmanager.mouse_event.connect(self.on_mouse_event)
        self.hintmanager.set_open_target.connect(self.set_force_open_target)
        self.signal_cache = SignalCache(uncached=['linkHovered'])
        self.page_.setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        self.page_.linkHovered.connect(self.linkHovered)
        self.linkClicked.connect(self.on_link_clicked)
        self.loadStarted.connect(
            lambda: modeman.maybe_leave('insert', 'load started'))
        self.loadFinished.connect(self.on_load_finished)
        # FIXME find some way to hide scrollbars without setScrollBarPolicy

    def _init_neighborlist(self):
        """Initialize the _zoom neighborlist."""
        self._zoom = NeighborList(
            config.get('general', 'zoom-levels'),
            default=config.get('general', 'default-zoom'),
            mode=NeighborList.Modes.block)

    def _on_destroyed(self, sender):
        """Called when a subsystem has been destroyed during shutdown.

        Args:
            sender: The object which called the callback.
        """
        self._destroyed[sender] = True
        dbgout = '\n'.join(['{}: {}'.format(k.__class__.__name__, v)
                           for (k, v) in self._destroyed.items()])
        logging.debug("{} has been destroyed, new status:\n{}".format(
            sender.__class__.__name__, dbgout))
        if all(self._destroyed.values()):
            if self._shutdown_callback is not None:
                logging.debug("Everything destroyed, calling callback")
                self._shutdown_callback()

    def _is_editable(self, hitresult):
        """Check if a hit result needs keyboard focus.

        Args:
            hitresult: A QWebHitTestResult
        """
        # FIXME is this algorithm accurate?
        if hitresult.isContentEditable():
            # text fields and the like
            return True
        if not config.get('input', 'insert-mode-on-plugins'):
            return False
        elem = hitresult.element()
        tag = elem.tagName().lower()
        if tag in ['embed', 'applet']:
            # Flash/Java/...
            return True
        if tag == 'object':
            # Could be Flash/Java/..., could be image/audio/...
            if not elem.hasAttribute('type'):
                logging.debug("<object> without type clicked...")
                return False
            objtype = elem.attribute('type')
            if (objtype.startswith('application/') or
                    elem.hasAttribute('classid')):
                # Let's hope flash/java stuff has an application/* mimetype OR
                # at least a classid attribute. Oh, and let's home images/...
                # DON"T have a classid attribute. HTML sucks.
                logging.debug("<object type=\"{}\"> clicked.".format(objtype))
                return True
        return False

    def openurl(self, url):
        """Open an URL in the browser.

        Args:
            url: The URL to load, as string or QUrl.

        Return:
            Return status of self.load

        Emit:
            titleChanged and urlChanged
        """
        try:
            u = urlutils.fuzzy_url(url)
        except urlutils.SearchEngineError as e:
            message.error(str(e))
            return
        logging.debug("New title: {}".format(urlutils.urlstring(u)))
        self.titleChanged.emit(urlutils.urlstring(u))
        self.urlChanged.emit(urlutils.qurl(u))
        return self.load(u)

    def zoom_perc(self, perc, fuzzyval=True):
        """Zoom to a given zoom percentage.

        Args:
            perc: The zoom percentage as int.
            fuzzyval: Whether to set the NeighborLists fuzzyval.
        """
        if fuzzyval:
            self._zoom.fuzzyval = int(perc)
        self.setZoomFactor(float(perc) / 100)
        message.info("Zoom level: {}%".format(perc))

    def zoom(self, offset):
        """Increase/Decrease the zoom level.

        Args:
            offset: The offset in the zoom level list.
        """
        level = self._zoom.getitem(offset)
        self.zoom_perc(level, fuzzyval=False)

    def shutdown(self, callback=None):
        """Shut down the tab cleanly and remove it.

        Inspired by [1].

        [1] https://github.com/integricho/path-of-a-pyqter/tree/master/qttut08

        Args:
            callback: Function to call after shutting down.
        """
        self._shutdown_callback = callback
        try:
            # Avoid loading finished signal when stopping
            self.loadFinished.disconnect()
        except TypeError:
            logging.exception("This should never happen.")
        self.stop()
        self.close()
        self.settings().setAttribute(QWebSettings.JavascriptEnabled, False)

        self._destroyed[self.page_] = False
        self.page_.destroyed.connect(functools.partial(self._on_destroyed,
                                                       self.page_))
        self.page_.deleteLater()

        self._destroyed[self] = False
        self.destroyed.connect(functools.partial(self._on_destroyed, self))
        self.deleteLater()
        logging.debug("Tab shutdown scheduled")

    @pyqtSlot(str)
    def on_link_clicked(self, url):
        """Handle a link.

        Called from the linkClicked signal. Checks if it should open it in a
        tab (middle-click or control) or not, and does so.

        Args:
            url: The url to handle, as string or QUrl.
        """
        if self._open_target == Target.tab:
            self.tabbedbrowser.tabopen(url, False)
        elif self._open_target == Target.bgtab:
            self.tabbedbrowser.tabopen(url, True)
        else:
            self.openurl(url)

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update tab config when config was changed."""
        if section == 'general' and option in ['zoom-levels', 'default-zoom']:
            self._init_neighborlist()

    @pyqtSlot('QMouseEvent')
    def on_mouse_event(self, evt):
        """Post a new mouseevent from a hintmanager."""
        self.setFocus()
        QApplication.postEvent(self, evt)

    @pyqtSlot(bool)
    def on_load_finished(self, _ok):
        """Handle auto-insert-mode after loading finished."""
        if not config.get('input', 'auto-insert-mode'):
            return
        frame = self.page_.currentFrame()
        elem = frame.findFirstElement(
            webelem.SELECTORS[webelem.Group.editable_focused])
        logging.debug("focus element: {}".format(not elem.isNull()))
        if elem.isNull():
            modeman.maybe_leave('insert', 'load finished')
        else:
            modeman.enter('insert', 'load finished')

    @pyqtSlot(str)
    def set_force_open_target(self, target):
        """Change the forced link target. Setter for _force_open_target.

        Args:
            target: A string to set self._force_open_target to.
        """
        t = getattr(Target, target)
        logging.debug("Setting force target to {}/{}".format(target, t))
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
            logging.warn("WebModalDialog requested, but we don't support "
                         "that!")
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
        frame = self.page_.mainFrame()
        new_pos = (frame.scrollBarValue(Qt.Horizontal),
                   frame.scrollBarValue(Qt.Vertical))
        if self._scroll_pos != new_pos:
            self._scroll_pos = new_pos
            logging.debug("Updating scroll position")
            m = (frame.scrollBarMaximum(Qt.Horizontal),
                 frame.scrollBarMaximum(Qt.Vertical))
            perc = (round(100 * new_pos[0] / m[0]) if m[0] != 0 else 0,
                    round(100 * new_pos[1] / m[1]) if m[1] != 0 else 0)
            self.scroll_pos_changed.emit(*perc)
        # Let superclass handle the event
        return super().paintEvent(e)

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
        pos = e.pos()
        frame = self.page_.frameAt(pos)
        if frame is None:
            # This happens when we click inside the webview, but not actually
            # on the QWebPage - for example when clicking the scrollbar
            # sometimes.
            logging.debug("Clicked at {} but frame is None!".format(pos))
            return super().mousePressEvent(e)
        pos -= frame.geometry().topLeft()
        hitresult = frame.hitTestContent(pos)
        if self._is_editable(hitresult):
            logging.debug("Clicked editable element!")
            modeman.enter('insert', 'click')
        else:
            logging.debug("Clicked non-editable element!")
            try:
                modeman.leave('insert', 'click')
            except ValueError:
                pass

        if self._force_open_target is not None:
            self._open_target = self._force_open_target
            self._force_open_target = None
            logging.debug("Setting force target: {}".format(
                Target[self._open_target]))
        elif (e.button() == Qt.MidButton or
              e.modifiers() & Qt.ControlModifier):
            if config.get('general', 'background-tabs'):
                self._open_target = Target.bgtab
            else:
                self._open_target = Target.tab
            logging.debug("Middle click, setting target: {}".format(
                Target[self._open_target]))
        else:
            self._open_target = Target.normal
            logging.debug("Normal click, setting normal target")
        return super().mousePressEvent(e)
