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

"""The main browser widget.

Defines BrowserTab (our own QWebView subclass) and TabbedBrowser (a TabWidget
containing BrowserTabs).

"""

import logging
import functools

import sip
from PyQt5.QtWidgets import QApplication, QShortcut, QSizePolicy
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QEvent
from PyQt5.QtGui import QClipboard
from PyQt5.QtPrintSupport import QPrintPreviewDialog
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkReply
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebView, QWebPage

import qutebrowser.utils.about as about
import qutebrowser.utils.url as urlutils
import qutebrowser.utils.config as config
from qutebrowser.widgets.tabbar import TabWidget
from qutebrowser.utils.signals import SignalCache, dbg_signal
from qutebrowser.utils.misc import read_file
from qutebrowser.utils.types import NeighborList


class TabbedBrowser(TabWidget):

    """A TabWidget with QWebViews inside.

    Provides methods to manage tabs, convenience methods to interact with the
    current tab (cur_*) and filters signals to re-emit them when they occured
    in the currently visible tab.

    For all tab-specific signals (cur_*) emitted by a tab, this happens:
       - the signal gets added to a signal_cache of the tab, so it can be
         emitted again if the current tab changes.
       - the signal gets filtered with _filter_signals and self.cur_* gets
         emitted if the signal occured in the current tab.

    Attributes:
        _url_stack: Stack of URLs of closed tabs.
        _space: Space QShortcut to avoid garbage collection
        _tabs: A list of open tabs.

    Signals:
        cur_progress: Progress of the current tab changed (loadProgress).
        cur_load_started: Current tab started loading (loadStarted)
        cur_load_finished: Current tab finished loading (loadFinished)
        cur_statusbar_message: Current tab got a statusbar message
                               (statusBarMessage)
        cur_tmp_message: Current tab needs to show a temporary message.
        cur_url_changed: Current URL changed (urlChanged)
        cur_link_hovered: Link hovered in current tab (linkHovered)
        cur_scroll_perc_changed: Scroll percentage of current tab changed.
                                 arg 1: x-position in %.
                                 arg 2: y-position in %.
        keypress: A key was pressed.
                  arg: The QKeyEvent leading to the keypress.
        shutdown_complete: The shuttdown is completed.
        quit: The last tab was closed, quit application.
        resized: Emitted when the browser window has resized, so the completion
                 widget can adjust its size to it.
                 arg: The new size.

    """

    cur_progress = pyqtSignal(int)
    cur_load_started = pyqtSignal()
    cur_load_finished = pyqtSignal(bool)
    cur_temp_message = pyqtSignal(str)
    cur_statusbar_message = pyqtSignal(str)
    cur_url_changed = pyqtSignal('QUrl')
    cur_link_hovered = pyqtSignal(str, str, str)
    cur_scroll_perc_changed = pyqtSignal(int, int)
    set_cmd_text = pyqtSignal(str)
    keypress = pyqtSignal('QKeyEvent')
    shutdown_complete = pyqtSignal()
    quit = pyqtSignal()
    resized = pyqtSignal('QRect')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(lambda idx:
                                    self.widget(idx).signal_cache.replay())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tabs = []
        self._url_stack = []
        self._space = QShortcut(self)
        self._space.setKey(Qt.Key_Space)
        self._space.setContext(Qt.WidgetWithChildrenShortcut)
        self._space.activated.connect(lambda: self.cur_scroll_page(0, 1))

    def _cb_tab_shutdown(self, tab):
        """Called after a tab has been shut down completely.

        Args:
            tab: The tab object which has been shut down.

        Emit:
            shutdown_complete: When the tab shutdown is done completely.

        """
        try:
            self._tabs.remove(tab)
        except ValueError:
            logging.exception("tab {} could not be removed".format(tab))
        logging.debug("Tabs after removing: {}".format(self._tabs))
        if not self._tabs:  # all tabs shut down
            logging.debug("Tab shutdown complete.")
            self.shutdown_complete.emit()

    def _cur_scroll_percent(self, perc=None, count=None, orientation=None):
        """Inner logic for cur_scroll_percent_(x|y).

        Args:
            perc: How many percent to scroll, or None
            count: How many percent to scroll, or None
            orientation: Qt.Horizontal or Qt.Vertical

        """
        if perc is None and count is None:
            perc = 100
        elif perc is None:
            perc = int(count)
        else:
            perc = float(perc)
        frame = self.currentWidget().page_.mainFrame()
        m = frame.scrollBarMaximum(orientation)
        if m == 0:
            return
        frame.setScrollBarValue(orientation, int(m * perc / 100))

    def _widget(self, count=None):
        """Return a widget based on a count/idx.

        Args:
            count: The tab index, or None.

        Return:
            The current widget if count is None.
            The widget with the given tab ID if count is given.
            None if no widget was found.

        """
        if count is None:
            return self.currentWidget()
        elif 1 <= count <= self.count():
            return self.widget(count - 1)
        else:
            return None

    def _titleChanged_handler(self, text):
        """Set the title of a tab.

        Slot for the titleChanged signal of any tab.

        Args:
            text: The text to set.

        """
        logging.debug('title changed to "{}"'.format(text))
        if text:
            self.setTabText(self.indexOf(self.sender()), text)
        else:
            logging.debug('ignoring title change')

    def _filter_factory(self, signal):
        """Factory for partial _filter_signals functions.

        Args:
            signal: The pyqtSignal to filter.

        Return:
            A partial functon calling _filter_signals with a signal.

        """
        return functools.partial(self._filter_signals, signal)

    def _filter_signals(self, signal, *args):
        """Filter signals and trigger TabbedBrowser signals if needed.

        Triggers signal if the original signal was sent from the _current_ tab
        and not from any other one.

        The original signal does not matter, since we get the new signal and
        all args.

        The current value of the signal is also stored in tab.signal_cache so
        it can be emitted later when the tab changes to the current tab.

        Args:
            signal: The signal to emit if the sender was the current widget.
            *args: The args to pass to the signal.

        Emit:
            The target signal if the sender was the current widget.

        """
        # FIXME BUG the signal cache ordering seems to be weird sometimes.
        # How to reproduce:
        #   - Open tab
        #   - While loading, open another tab
        #   - Switch back to #1 when loading finished
        #   - It seems loadingStarted is before loadingFinished
        sender = self.sender()
        log_signal = not signal.signal.startswith('2cur_progress')
        if log_signal:
            logging.debug('signal {} (tab {})'.format(dbg_signal(signal, args),
                                                      self.indexOf(sender)))
        if not isinstance(sender, BrowserTab):
            # FIXME why does this happen?
            logging.warn('Got signal {} by {} which is no tab!'.format(
                dbg_signal(signal, args), sender))
            return
        sender.signal_cache.add(signal, args)
        if self.currentWidget() == sender:
            if log_signal:
                logging.debug('  emitting')
            return signal.emit(*args)
        else:
            if log_signal:
                logging.debug('  ignoring')

    def shutdown(self):
        """Try to shut down all tabs cleanly.

        Emit:
            shutdown_complete if the shutdown completed successfully.

        """
        try:
            self.currentChanged.disconnect()
        except TypeError:
            pass
        tabcount = self.count()
        if tabcount == 0:
            logging.debug("No tabs -> shutdown complete")
            self.shutdown_complete.emit()
            return
        for tabidx in range(tabcount):
            logging.debug("Shutting down tab {}/{}".format(tabidx, tabcount))
            tab = self.widget(tabidx)
            tab.shutdown(callback=functools.partial(self._cb_tab_shutdown,
                                                    tab))

    def tabopen(self, url):
        """Open a new tab with a given url.

        Also connect all the signals we need to _filter_signals.

        Args:
            url: The URL to open.

        """
        logging.debug("Opening {}".format(url))
        url = urlutils.qurl(url)
        tab = BrowserTab(self)
        self._tabs.append(tab)
        self.addTab(tab, urlutils.urlstring(url))
        self.setCurrentWidget(tab)
        tab.linkHovered.connect(self._filter_factory(self.cur_link_hovered))
        tab.loadProgress.connect(self._filter_factory(self.cur_progress))
        tab.loadFinished.connect(self._filter_factory(self.cur_load_finished))
        tab.loadStarted.connect(lambda:  # pylint: disable=unnecessary-lambda
                                self.sender().signal_cache.clear())
        tab.loadStarted.connect(self._filter_factory(self.cur_load_started))
        tab.statusBarMessage.connect(
            self._filter_factory(self.cur_statusbar_message))
        tab.scroll_pos_changed.connect(
            self._filter_factory(self.cur_scroll_perc_changed))
        tab.urlChanged.connect(self._filter_factory(self.cur_url_changed))
        tab.titleChanged.connect(self._titleChanged_handler)
        # FIXME sometimes this doesn't load
        tab.show()
        tab.open_tab.connect(self.tabopen)
        tab.openurl(url)

    def tabopencur(self):
        """Set the statusbar to :tabopen and the current URL.

        Emit:
            set_cmd_text prefilled with :tabopen $URL

        """
        url = urlutils.urlstring(self.currentWidget().url())
        self.set_cmd_text.emit(':tabopen ' + url)

    def opencur(self):
        """Set the statusbar to :open and the current URL.

        Emit:
            set_cmd_text prefilled with :open $URL

        """
        url = urlutils.urlstring(self.currentWidget().url())
        self.set_cmd_text.emit(':open ' + url)

    def undo_close(self):
        """Undo closing a tab.

        Command handler for :undo.

        """
        if self._url_stack:
            self.tabopen(self._url_stack.pop())

    def cur_close(self, count=None):
        """Close the current/[count]th tab.

        Command handler for :close.

        Args:
            count: The tab index to close, or None

        Emit:
            quit: If last tab was closed and last_close in config is set to
                  quit.

        """
        idx = self.currentIndex() if count is None else count - 1
        tab = self._widget(count)
        if tab is None:
            return
        last_close = config.config.get('tabbar', 'last_close')
        if self.count() > 1:
            # FIXME maybe we actually should store the webview objects here
            self._url_stack.append(tab.url())
            self.removeTab(idx)
            tab.shutdown(callback=functools.partial(self._cb_tab_shutdown,
                                                    tab))
        elif last_close == 'quit':
            self.quit.emit()
        elif last_close == 'blank':
            tab.openurl('about:blank')

    def openurl(self, url, count=None):
        """Open an url in the current/[count]th tab.

        Command handler for :open.

        Args:
            url: The URL to open.
            count: The tab index to open the URL in, or None.

        """
        tab = self._widget(count)
        if tab is not None:
            tab.openurl(url)

    def cur_reload(self, count=None):
        """Reload the current/[count]th tab.

        Command handler for :reload.

        Args:
            count: The tab index to reload, or None.

        """
        tab = self._widget(count)
        if tab is not None:
            tab.reload()

    def cur_stop(self, count=None):
        """Stop loading in the current/[count]th tab.

        Command handler for :stop.

        Args:
            count: The tab index to stop, or None.

        """
        tab = self._widget(count)
        if tab is not None:
            tab.stop()

    def cur_print(self, count=None):
        """Print the current/[count]th tab.

        Command handler for :print.

        Args:
            count: The tab index to print, or None.

        """
        # FIXME that does not what I expect
        tab = self._widget(count)
        if tab is not None:
            preview = QPrintPreviewDialog(self)
            preview.paintRequested.connect(tab.print)
            preview.exec_()

    def cur_back(self, count=1):
        """Go back in the history of the current tab.

        Command handler for :back.

        Args:
            count: How many pages to go back.

        """
        # FIXME display warning if beginning of history
        for i in range(count):  # pylint: disable=unused-variable
            self.currentWidget().back()

    def cur_forward(self, count=1):
        """Go forward in the history of the current tab.

        Command handler for :forward.

        Args:
            count: How many pages to go forward.

        """
        # FIXME display warning if end of history
        for i in range(count):  # pylint: disable=unused-variable
            self.currentWidget().forward()

    @pyqtSlot(str, int)
    def cur_search(self, text, flags):
        """Search for text in the current page.

        Args:
            text: The text to search for.
            flags: The QWebPage::FindFlags.

        """
        self.currentWidget().findText(text, flags)

    def cur_scroll(self, dx, dy, count=1):
        """Scroll the current tab by count * dx/dy.

        Command handler for :scroll.

        Args:
            dx: How much to scroll in x-direction.
            dy: How much to scroll in x-direction.
            count: multiplier

        """
        dx = int(count) * float(dx)
        dy = int(count) * float(dy)
        self.currentWidget().page_.mainFrame().scroll(dx, dy)

    def cur_scroll_percent_x(self, perc=None, count=None):
        """Scroll the current tab to a specific percent of the page.

        Command handler for :scroll_perc_x.

        Args:
            perc: Percentage to scroll.
            count: Percentage to scroll.

        """
        self._cur_scroll_percent(perc, count, Qt.Horizontal)

    def cur_scroll_percent_y(self, perc=None, count=None):
        """Scroll the current tab to a specific percent of the page.

        Command handler for :scroll_perc_y

        Args:
            perc: Percentage to scroll.
            count: Percentage to scroll.

        """
        self._cur_scroll_percent(perc, count, Qt.Vertical)

    def cur_scroll_page(self, mx, my, count=1):
        """Scroll the frame page-wise.

        Args:
            mx: How many pages to scroll to the right.
            my: How many pages to scroll down.
            count: multiplier

        """
        # FIXME this might not work with HTML frames
        page = self.currentWidget().page_
        size = page.viewportSize()
        page.mainFrame().scroll(int(count) * float(mx) * size.width(),
                                int(count) * float(my) * size.height())

    def cur_yank(self, sel=False):
        """Yank the current url to the clipboard or primary selection.

        Command handler for :yank.

        Args:
            sel: True to use primary selection, False to use clipboard

        Emit:
            cur_temp_message to display a temporary message.

        """
        clip = QApplication.clipboard()
        url = urlutils.urlstring(self.currentWidget().url())
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        clip.setText(url, mode)
        self.cur_temp_message.emit('URL yanked to {}'.format(
            'primary selection' if sel else 'clipboard'))

    def cur_yank_title(self, sel=False):
        """Yank the current title to the clipboard or primary selection.

        Command handler for :yanktitle.

        Args:
            sel: True to use primary selection, False to use clipboard

        Emit:
            cur_temp_message to display a temporary message.

        """
        clip = QApplication.clipboard()
        title = self.tabText(self.currentIndex())
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        clip.setText(title, mode)
        self.cur_temp_message.emit('Title yanked to {}'.format(
            'primary selection' if sel else 'clipboard'))

    def switch_prev(self, count=1):
        """Switch to the ([count]th) previous tab.

        Command handler for :tabprev.

        Args:
            count: How many tabs to switch back.

        """
        idx = self.currentIndex()
        if idx - count >= 0:
            self.setCurrentIndex(idx - count)
        else:
            # FIXME
            pass

    def switch_next(self, count=1):
        """Switch to the ([count]th) next tab.

        Command handler for :tabnext.

        Args:
            count: How many tabs to switch forward.

        """
        idx = self.currentIndex()
        if idx + count < self.count():
            self.setCurrentIndex(idx + count)
        else:
            # FIXME
            pass

    def paste(self, sel=False):
        """Open a page from the clipboard.

        Command handler for :paste.

        Args:
            sel: True to use primary selection, False to use clipboard

        """
        # FIXME what happens for invalid URLs?
        clip = QApplication.clipboard()
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        url = clip.text(mode)
        logging.debug("Clipboard contained: '{}'".format(url))
        self.openurl(url)

    def tabpaste(self, sel=False):
        """Open a page from the clipboard in a new tab.

        Command handler for :paste.

        Args:
            sel: True to use primary selection, False to use clipboard

        """
        # FIXME what happens for invalid URLs?
        clip = QApplication.clipboard()
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        url = clip.text(mode)
        logging.debug("Clipboard contained: '{}'".format(url))
        self.tabopen(url)

    def keyPressEvent(self, e):
        """Extend TabWidget (QWidget)'s keyPressEvent to emit a signal.

        Args:
            e: The QKeyPressEvent

        Emit:
            keypress: Always emitted.

        """
        self.keypress.emit(e)
        super().keyPressEvent(e)

    def resizeEvent(self, e):
        """Extend resizeEvent of QWidget to emit a resized signal afterwards.

        Args:
            e: The QResizeEvent

        Emit:
            resize: Always emitted.

        """
        super().resizeEvent(e)
        self.resized.emit(self.geometry())


class BrowserTab(QWebView):

    """One browser tab in TabbedBrowser.

    Our own subclass of a QWebView with some added bells and whistles.

    Attributes:
        page_: The QWebPage behind the view
        signal_cache: The signal cache associated with the view.
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

    """

    scroll_pos_changed = pyqtSignal(int, int)
    open_tab = pyqtSignal('QUrl')
    linkHovered = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scroll_pos = (-1, -1)
        self._shutdown_callback = None
        self._open_new_tab = False
        self._destroyed = {}
        self.page_ = BrowserPage(self)
        self.setPage(self.page_)
        self.signal_cache = SignalCache(uncached=['linkHovered'])
        self.page_.setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        self.page_.linkHovered.connect(self.linkHovered)
        self.linkClicked.connect(self.on_link_clicked)
        # FIXME find some way to hide scrollbars without setScrollBarPolicy

    def openurl(self, url):
        """Open an URL in the browser.

        Args:
            url: The URL to load, as string or QUrl.

        Return:
            Return status of self.load

        Emit:
            titleChanged and urlChanged

        """
        u = urlutils.fuzzy_url(url)
        logging.debug('New title: {}'.format(urlutils.urlstring(u)))
        self.titleChanged.emit(urlutils.urlstring(u))
        self.urlChanged.emit(urlutils.qurl(u))
        if urlutils.is_about_url(u):
            try:
                content = about.handle(urlutils.urlstring(u))
            except AttributeError:
                return self.load(u)
            else:
                self.setUrl(u)
                self.setContent(content, 'text/html')
        else:
            return self.load(u)

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


class BrowserPage(QWebPage):

    """Our own QWebPage with advanced features.

    Attributes:
        _extension_handlers: Mapping of QWebPage extensions to their handlers.
        network_access_manager: The QNetworkAccessManager used.

    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._extension_handlers = {
            QWebPage.ErrorPageExtension: self._handle_errorpage,
        }
        self.network_access_manager = NetworkManager(self)
        self.setNetworkAccessManager(self.network_access_manager)

    def _handle_errorpage(self, opt, out):
        """Display an error page if needed.

        Loosly based on Helpviewer/HelpBrowserWV.py from eric5
        (line 260 @ 5d937eb378dd)

        Args:
            opt: The QWebPage.ErrorPageExtensionOption instance.
            out: The QWebPage.ErrorPageExtensionReturn instance to write return
                 values to.

        Return:
            False if no error page should be displayed, True otherwise.

        """
        info = sip.cast(opt, QWebPage.ErrorPageExtensionOption)
        errpage = sip.cast(out, QWebPage.ErrorPageExtensionReturn)
        errpage.baseUrl = info.url
        if (info.domain == QWebPage.QtNetwork and
                info.error == QNetworkReply.OperationCanceledError):
            return False
        urlstr = urlutils.urlstring(info.url)
        title = "Error loading page: {}".format(urlstr)
        errpage.content = read_file('html/error.html').format(
            title=title, url=urlstr, error=info.errorString, icon='')
        return True

    def supportsExtension(self, ext):
        """Override QWebPage::supportsExtension to provide error pages.

        Args:
            ext: The extension to check for.

        Return:
            True if the extension can be handled, False otherwise.

        """
        return ext in self._extension_handlers

    def extension(self, ext, opt, out):
        """Override QWebPage::extension to provide error pages.

        Args:
            ext: The extension.
            opt: Extension options instance.
            out: Extension output instance.

        Return:
            Handler return value.

        """
        try:
            handler = self._extension_handlers[ext]
        except KeyError:
            return super().extension(ext, opt, out)
        return handler(opt, out)


class NetworkManager(QNetworkAccessManager):

    """Our own QNetworkAccessManager.

    Attributes:
        _requests: Pending requests.

    """

    def __init__(self, parent=None):
        self._requests = {}
        super().__init__(parent)

    def abort_requests(self):
        """Abort all running requests."""
        for request in self._requests.values():
            request.abort()

    def createRequest(self, op, req, outgoing_data):
        """Return a new QNetworkReply object.

        Extend QNetworkAccessManager::createRequest to save requests in
        self._requests.

        Args:
             op: Operation op
             req: const QNetworkRequest & req
             outgoing_data: QIODevice * outgoingData

        Return:
            A QNetworkReply.

        """
        reply = super().createRequest(op, req, outgoing_data)
        self._requests[id(reply)] = reply
        reply.destroyed.connect(lambda obj: self._requests.pop(id(obj)))
        return reply
