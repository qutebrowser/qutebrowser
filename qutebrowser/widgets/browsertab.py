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

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QEvent
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebView, QWebPage

import qutebrowser.utils.url as urlutils
import qutebrowser.config.config as config
import qutebrowser.utils.message as message
from qutebrowser.widgets.browserpage import BrowserPage
from qutebrowser.utils.signals import SignalCache
from qutebrowser.utils.usertypes import NeighborList


class BrowserTab(QWebView):

    """One browser tab in TabbedBrowser.

    Our own subclass of a QWebView with some added bells and whistles.

    Attributes:
        page_: The QWebPage behind the view
        signal_cache: The signal cache associated with the view.
        _zoom: A NeighborList with the zoom levels.
        _scroll_pos: The old scroll position.
        _shutdown_callback: Callback to be called after shutdown.
        _open_new_tab: Whether to open a new tab for the next action.
        _shutdown_callback: The callback to call after shutting down.
        _destroyed: Dict of all items to be destroyed on shtudown.

    Signals:
        scroll_pos_changed: Scroll percentage of current tab changed.
                            arg 1: x-position in %.
                            arg 2: y-position in %.
        open_tab: A new tab should be opened.
                  arg: The address to open
        linkHovered: QWebPages linkHovered signal exposed.
        temp_message: Show a temporary message in the statusbar.
                      arg: Message to be shown.
    """

    scroll_pos_changed = pyqtSignal(int, int)
    open_tab = pyqtSignal('QUrl')
    linkHovered = pyqtSignal(str, str, str)
    temp_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scroll_pos = (-1, -1)
        self._shutdown_callback = None
        self._open_new_tab = False
        self._destroyed = {}
        self._zoom = None
        self._init_neighborlist()
        self.page_ = BrowserPage(self)
        self.setPage(self.page_)
        self.signal_cache = SignalCache(uncached=['linkHovered'])
        self.page_.setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        self.page_.linkHovered.connect(self.linkHovered)
        self.linkClicked.connect(self.on_link_clicked)
        # FIXME find some way to hide scrollbars without setScrollBarPolicy

    def _init_neighborlist(self):
        """Initialize the _zoom neighborlist."""
        self._zoom = NeighborList(
            config.config.get('general', 'zoomlevels'),
            default=config.config.get('general', 'defaultzoom'),
            mode=NeighborList.BLOCK)

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
        logging.debug('New title: {}'.format(urlutils.urlstring(u)))
        self.titleChanged.emit(urlutils.urlstring(u))
        self.urlChanged.emit(urlutils.qurl(u))
        return self.load(u)

    def zoom(self, offset):
        """Increase/Decrease the zoom level.

        Args:
            offset: The offset in the zoom level list.

        Emit:
            temp_message: Emitted with new zoom level.
        """
        level = self._zoom.getitem(offset)
        self.setZoomFactor(float(level) / 100)
        self.temp_message.emit("Zoom level: {}%".format(level))

    @pyqtSlot(str)
    def on_link_clicked(self, url):
        """Handle a link.

        Called from the linkClicked signal. Checks if it should open it in a
        tab (middle-click or control) or not, and does so.

        Args:
            url: The url to handle, as string or QUrl.

        Emit:
            open_tab: Emitted if window should be opened in a new tab.
        """
        if self._open_new_tab:
            self.open_tab.emit(url)
        else:
            self.openurl(url)

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

        netman = self.page_.network_access_manager
        self._destroyed[netman] = False
        netman.abort_requests()
        netman.destroyed.connect(functools.partial(self._on_destroyed, netman))
        netman.deleteLater()
        logging.debug("Tab shutdown scheduled")

    def on_config_changed(self, section, option):
        """Update tab config when config was changed."""
        if section == 'general' and option in ['zoomlevels', 'defaultzoom']:
            self._init_neighborlist()

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

    def paintEvent(self, e):
        """Extend paintEvent to emit a signal if the scroll position changed.

        This is a bit of a hack: We listen to repaint requests here, in the
        hope a repaint will always be requested when scrolling, and if the
        scroll position actually changed, we emit a signal.

        Args:
            e: The QPaintEvent.

        Emit:
            scroll_pos_changed; If the scroll position changed.
        """
        frame = self.page_.mainFrame()
        new_pos = (frame.scrollBarValue(Qt.Horizontal),
                   frame.scrollBarValue(Qt.Vertical))
        if self._scroll_pos != new_pos:
            self._scroll_pos = new_pos
            logging.debug("Updating scroll position")
            frame = self.page_.mainFrame()
            m = (frame.scrollBarMaximum(Qt.Horizontal),
                 frame.scrollBarMaximum(Qt.Vertical))
            perc = (round(100 * new_pos[0] / m[0]) if m[0] != 0 else 0,
                    round(100 * new_pos[1] / m[1]) if m[1] != 0 else 0)
            self.scroll_pos_changed.emit(*perc)
        # Let superclass handle the event
        return super().paintEvent(e)

    def event(self, e):
        """Check if a link was clicked with the middle button or Ctrl.

        Extend the superclass event().

        This also is a bit of a hack, but it seems it's the only possible way.
        Set the _open_new_tab attribute accordingly.

        Args:
            e: The arrived event.

        Return:
            The superclass event return value.
        """
        if e.type() in [QEvent.MouseButtonPress, QEvent.MouseButtonDblClick]:
            self._open_new_tab = (e.button() == Qt.MidButton or
                                  e.modifiers() & Qt.ControlModifier)
        return super().event(e)
