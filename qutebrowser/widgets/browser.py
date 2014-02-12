"""The main browser widget.

Defines BrowserTab (our own QWebView subclass) and TabbedBrowser (a TabWidget
containing BrowserTabs).

"""

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

import logging
import functools

from PyQt5.QtWidgets import QShortcut, QApplication, QSizePolicy
from PyQt5.QtCore import pyqtSignal, Qt, QEvent
from PyQt5.QtGui import QClipboard
from PyQt5.QtPrintSupport import QPrintPreviewDialog
from PyQt5.QtWebKitWidgets import QWebView, QWebPage

import qutebrowser.utils.about as about
import qutebrowser.utils.config as config
import qutebrowser.utils.url as urlutils
from qutebrowser.widgets.tabbar import TabWidget
from qutebrowser.utils.signals import dbg_signal, SignalCache


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

    """

    cur_progress = pyqtSignal(int)  # Progress of the current tab changed
    cur_load_started = pyqtSignal()  # Current tab started loading
    cur_load_finished = pyqtSignal(bool)  # Current tab finished loading
    cur_statusbar_message = pyqtSignal(str)  # Status bar message
    cur_url_changed = pyqtSignal('QUrl')  # Current URL changed
    cur_link_hovered = pyqtSignal(str, str, str)  # Link hovered in cur tab
    # Current tab changed scroll position
    cur_scroll_perc_changed = pyqtSignal(int, int)
    set_cmd_text = pyqtSignal(str)  # Set commandline to a given text
    keypress = pyqtSignal('QKeyEvent')
    _url_stack = []  # Stack of URLs of closed tabs

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(lambda idx:
                                    self.widget(idx).signal_cache.replay())
        space = QShortcut(self)
        space.setKey(Qt.Key_Space)
        space.setContext(Qt.WidgetWithChildrenShortcut)
        space.activated.connect(self.space_scroll)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def tabopen(self, url):
        """Open a new tab with a given url.

        Also connect all the signals we need to _filter_signals.

        """
        logging.debug("Opening {}".format(url))
        url = urlutils.qurl(url)
        tab = BrowserTab(self)
        tab.openurl(url)
        self.cur_url_changed.emit(url)
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
        tab.open_tab.connect(self.tabopen)

    def tabopencur(self):
        """Set the statusbar to :tabopen and the current URL."""
        url = urlutils.urlstring(self.currentWidget().url())
        self.set_cmd_text.emit(':tabopen ' + url)

    def openurl(self, url, count=None):
        """Open an url in the current/[count]th tab.

        Command handler for :open.
        url -- The URL to open.

        """
        tab = self._widget(count)
        if tab is not None:
            tab.openurl(url)

    def opencur(self):
        """Set the statusbar to :open and the current URL."""
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

        """
        if self.count() > 1:
            idx = self.currentIndex() if count is None else count - 1
            tab = self._widget(count)
            if tab is not None:
                # FIXME maybe we actually should store the webview objects here
                self._url_stack.append(tab.url())
                self.removeTab(idx)
        else:
            # FIXME
            pass

    def cur_reload(self, count=None):
        """Reload the current/[count]th tab.

        Command handler for :reload.

        """
        tab = self._widget(count)
        if tab is not None:
            tab.reload()

    def cur_stop(self, count=None):
        """Stop loading in the current/[count]th tab.

        Command handler for :stop.

        """
        tab = self._widget(count)
        if tab is not None:
            tab.stop()

    def cur_print(self, count=None):
        """Print the current/[count]th tab.

        Command handler for :print.

        """
        # FIXME that does not what I expect
        tab = self._widget(count)
        if tab is not None:
            preview = QPrintPreviewDialog()
            preview.paintRequested.connect(tab.print)
            preview.exec_()

    def cur_back(self, count=1):
        """Go back in the history of the current tab.

        Go back for 1 page if count is unset, else go back [count] pages.
        Command handler for :back.

        """
        # FIXME display warning if beginning of history
        for i in range(count):  # pylint: disable=unused-variable
            self.currentWidget().back()

    def cur_forward(self, count=1):
        """Go forward in the history of the current tab.

        Go forward for 1 page if count is unset, else go forward [count] pages.
        Command handler for :forward.

        """
        # FIXME display warning if end of history
        for i in range(count):  # pylint: disable=unused-variable
            self.currentWidget().forward()

    def cur_search(self, text, flags):
        """Search for text in the current page.

        text  -- The text to search for.
        flags -- The QWebPage::FindFlags.

        """
        self.currentWidget().findText(text, flags)

    def cur_scroll(self, dx, dy, count=1):
        """Scroll the current tab by count * dx/dy.

        Command handler for :scroll.

        """
        dx = int(count) * int(dx)
        dy = int(count) * int(dy)
        self.currentWidget().page().mainFrame().scroll(dx, dy)

    def cur_scroll_percent_x(self, perc=None, count=None):
        """Scroll the current tab to a specific percent of the page.

        Accepts percentage either as argument, or as count.

        Command handler for :scroll_perc_x.

        """
        self._cur_scroll_percent(perc, count, Qt.Horizontal)

    def cur_scroll_percent_y(self, perc=None, count=None):
        """Scroll the current tab to a specific percent of the page.

        Accepts percentage either as argument, or as count.

        Command handler for :scroll_perc_y

        """
        self._cur_scroll_percent(perc, count, Qt.Vertical)

    def _cur_scroll_percent(self, perc=None, count=None, orientation=None):
        """Inner logic for cur_scroll_percent_(x|y)."""
        if perc is None and count is None:
            perc = 100
        elif perc is None:
            perc = int(count)
        else:
            perc = int(perc)
        frame = self.currentWidget().page().mainFrame()
        m = frame.scrollBarMaximum(orientation)
        if m == 0:
            return
        frame.setScrollBarValue(orientation, int(m * perc / 100))

    def switch_prev(self, count=1):
        """Switch to the ([count]th) previous tab.

        Command handler for :tabprev.

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

        """
        idx = self.currentIndex()
        if idx + count < self.count():
            self.setCurrentIndex(idx + count)
        else:
            # FIXME
            pass

    def space_scroll(self):
        """Scroll when space is pressed.

        This gets called from the space QShortcut in __init__.

        """
        try:
            amount = config.config['general']['space_scroll']
        except KeyError:
            amount = 200
        self.cur_scroll(0, amount)

    def cur_yank(self, sel=False):
        """Yank the current url to the clipboard or primary selection.

        Command handler for :yank.

        """
        clip = QApplication.clipboard()
        url = urlutils.urlstring(self.currentWidget().url())
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        clip.setText(url, mode)
        # FIXME provide visual feedback

    def cur_yank_title(self, sel=False):
        """Yank the current title to the clipboard or primary selection.

        Command handler for :yanktitle.

        """
        clip = QApplication.clipboard()
        title = self.tabText(self.currentIndex())
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        clip.setText(title, mode)
        # FIXME provide visual feedbac

    def paste(self, sel=False):
        """Open a page from the clipboard.

        Command handler for :paste.

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

        """
        # FIXME what happens for invalid URLs?
        clip = QApplication.clipboard()
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        url = clip.text(mode)
        logging.debug("Clipboard contained: '{}'".format(url))
        self.tabopen(url)

    def keyPressEvent(self, e):
        """Extend TabWidget (QWidget)'s keyPressEvent to emit a signal."""
        self.keypress.emit(e)
        super().keyPressEvent(e)

    def _widget(self, count=None):
        """Return a widget based on a count/idx.

        If count is None, return the current widget.

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

        """
        logging.debug('title changed to "{}"'.format(text))
        if text:
            self.setTabText(self.indexOf(self.sender()), text)
        else:
            logging.debug('ignoring title change')

    def _filter_factory(self, signal):
        """Return a partial functon calling _filter_signals with a signal."""
        return functools.partial(self._filter_signals, signal)

    def _filter_signals(self, signal, *args):
        """Filter signals and trigger TabbedBrowser signals if needed.

        Triggers signal if the original signal was sent from the _current_ tab
        and not from any other one.

        The original signal does not matter, since we get the new signal and
        all args.

        The current value of the signal is also stored in tab.signal_cache so
        it can be emitted later when the tab changes to the current tab.

        signal -- The signal to emit if the sender was the current widget.
        *args -- The args to pass to the signal.

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


class BrowserTab(QWebView):

    """One browser tab in TabbedBrowser.

    Our own subclass of a QWebView with some added bells and whistles.

    """

    progress = 0
    scroll_pos_changed = pyqtSignal(int, int)
    open_tab = pyqtSignal('QUrl')
    linkHovered = pyqtSignal(str, str, str)
    _scroll_pos = (-1, -1)
    _open_new_tab = False  # open new tab for the next action
    # dict of tab specific signals, and the values we last got from them.
    signal_cache = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signal_cache = SignalCache(uncached=['linkHovered'])
        self.loadProgress.connect(self.set_progress)
        self.page().setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        self.page().linkHovered.connect(self.linkHovered)
        self.installEventFilter(self)
        self.linkClicked.connect(self.link_handler)
        # FIXME find some way to hide scrollbars without setScrollBarPolicy
        self.show()

    def openurl(self, url):
        """Open an URL in the browser.

        url -- The URL to load, as string or QUrl.

        """
        u = urlutils.fuzzy_url(url)
        logging.debug('New title: {}'.format(urlutils.urlstring(u)))
        self.titleChanged.emit(urlutils.urlstring(u))
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

    def link_handler(self, url):
        """Handle a link.

        Called from the linkClicked signal. Checks if it should open it in a
        tab (middle-click or control) or not, and does so.

        url -- The url to handle, as string or QUrl.

        """
        if self._open_new_tab:
            self.open_tab.emit(url)
        else:
            self.openurl(url)

    def set_progress(self, prog):
        """Update the progress property if the loading progress changed.

        Slot for the loadProgress signal.

        prog -- New progress.

        """
        self.progress = prog

    def eventFilter(self, watched, e):
        """Dirty hack to emit a signal if the scroll position changed.

        We listen to repaint requests here, in the hope a repaint will always
        be requested when scrolling, and if the scroll position actually
        changed, we emit a signal.

        watched -- The watched Qt object.
        e -- The new event.

        """
        if watched == self and e.type() == QEvent.Paint:
            frame = self.page().mainFrame()
            new_pos = (frame.scrollBarValue(Qt.Horizontal),
                       frame.scrollBarValue(Qt.Vertical))
            if self._scroll_pos != new_pos:
                self._scroll_pos = new_pos
                logging.debug("Updating scroll position")
                frame = self.page().mainFrame()
                m = (frame.scrollBarMaximum(Qt.Horizontal),
                     frame.scrollBarMaximum(Qt.Vertical))
                perc = (round(100 * new_pos[0] / m[0]) if m[0] != 0 else 0,
                        round(100 * new_pos[1] / m[1]) if m[1] != 0 else 0)
                self.scroll_pos_changed.emit(*perc)
        # we're not actually filtering something, let superclass handle the
        # event
        return super().eventFilter(watched, e)

    def event(self, e):
        """Check if a link was clicked with the middle button or Ctrl.

        Extends the superclass event().

        This also is a bit of a hack, but it seems it's the only possible way.
        Set the _open_new_tab attribute accordingly.

        e -- The arrived event.

        """
        if e.type() in [QEvent.MouseButtonPress, QEvent.MouseButtonDblClick]:
            self._open_new_tab = (e.button() == Qt.MidButton or
                                  e.modifiers() & Qt.ControlModifier)
        return super().event(e)
