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

"""The main tabbed browser widget."""

import logging
import functools

from PyQt5.QtWidgets import QApplication, QShortcut, QSizePolicy
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QObject
from PyQt5.QtGui import QClipboard
from PyQt5.QtPrintSupport import QPrintPreviewDialog

import qutebrowser.utils.url as urlutils
import qutebrowser.config.config as config
import qutebrowser.commands.utils as cmdutils
from qutebrowser.widgets.tabbar import TabWidget
from qutebrowser.widgets.browsertab import BrowserTab
from qutebrowser.utils.signals import dbg_signal


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
        cur: A CurCommandDispatcher instance to dispatch commands to the
             current tab.

    Signals:
        cur_progress: Progress of the current tab changed (loadProgress).
        cur_load_started: Current tab started loading (loadStarted)
        cur_load_finished: Current tab finished loading (loadFinished)
        cur_statusbar_message: Current tab got a statusbar message
                               (statusBarMessage)
        cur_temp_message: Current tab needs to show a temporary message.
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
        self._space.activated.connect(lambda: self.cur.scroll_page(0, 1))
        self.cur = CurCommandDispatcher(self)
        self.cur.temp_message.connect(self.cur_temp_message)

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

    def cntwidget(self, count=None):
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

    @pyqtSlot(str, str, object)
    def on_config_changed(self, section, option, value):
        """Update tab config when config was changed."""
        super().on_config_changed(section, option, value)
        for tab in self._tabs:
            tab.on_config_changed(section, option, value)

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

    @cmdutils.register(instance='mainwindow.tabs')
    def tabclose(self, count=None):
        """Close the current/[count]th tab.

        Command handler for :close.

        Args:
            count: The tab index to close, or None

        Emit:
            quit: If last tab was closed and last_close in config is set to
                  quit.
        """
        idx = self.currentIndex() if count is None else count - 1
        tab = self.cntwidget(count)
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

    @cmdutils.register(instance='mainwindow.tabs', split_args=False)
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
        tab.temp_message.connect(self._filter_factory(self.cur_temp_message))
        tab.urlChanged.connect(self._filter_factory(self.cur_url_changed))
        tab.titleChanged.connect(self._titleChanged_handler)
        # FIXME sometimes this doesn't load
        tab.show()
        tab.open_tab.connect(self.tabopen)
        tab.openurl(url)

    @cmdutils.register(instance='mainwindow.tabs', hide=True)
    def tabopencur(self):
        """Set the statusbar to :tabopen and the current URL.

        Emit:
            set_cmd_text prefilled with :tabopen $URL
        """
        url = urlutils.urlstring(self.currentWidget().url())
        self.set_cmd_text.emit(':tabopen ' + url)

    @cmdutils.register(instance='mainwindow.tabs', hide=True)
    def opencur(self):
        """Set the statusbar to :open and the current URL.

        Emit:
            set_cmd_text prefilled with :open $URL
        """
        url = urlutils.urlstring(self.currentWidget().url())
        self.set_cmd_text.emit(':open ' + url)

    @cmdutils.register(instance='mainwindow.tabs', name='undo')
    def undo_close(self):
        """Switch to the previous tab, or skip [count] tabs.

        Command handler for :undo.
        """
        if self._url_stack:
            self.tabopen(self._url_stack.pop())

    @cmdutils.register(instance='mainwindow.tabs', name='tabprev')
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

    @cmdutils.register(instance='mainwindow.tabs', name='tabnext')
    def switch_next(self, count=1):
        """Switch to the next tab, or skip [count] tabs.

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

    @cmdutils.register(instance='mainwindow.tabs')
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
        self.cur.openurl(url)

    @cmdutils.register(instance='mainwindow.tabs')
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


class CurCommandDispatcher(QObject):

    """Command dispatcher for TabbedBrowser.

    Contains all commands which are related to the current tab.

    Attributes:
        tabs: The TabbedBrowser object.

    Signals:
        temp_message: Connected to TabbedBrowser signal.
    """

    # FIXME maybe subclassing would be more clean?

    temp_message = pyqtSignal(str)

    def __init__(self, parent):
        """Constructor.

        Uses setattr to get some methods from parent.

        Args:
            parent: The TabbedBrowser for this dispatcher.
        """
        super().__init__(parent)
        self.tabs = parent

    def _scroll_percent(self, perc=None, count=None, orientation=None):
        """Inner logic for scroll_percent_(x|y).

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
        frame = self.tabs.currentWidget().page_.mainFrame()
        m = frame.scrollBarMaximum(orientation)
        if m == 0:
            return
        frame.setScrollBarValue(orientation, int(m * perc / 100))

    @cmdutils.register(instance='mainwindow.tabs.cur', name='open',
                       split_args=False)
    def openurl(self, url, count=None):
        """Open an url in the current/[count]th tab.

        Command handler for :open.

        Args:
            url: The URL to open.
            count: The tab index to open the URL in, or None.
        """
        tab = self.tabs.cntwidget(count)
        if tab is None:
            if count is None:
                # We want to open an URL in the current tab, but none exists
                # yet.
                self.tabs.tabopen(url)
            else:
                # Explicit count with a tab that doesn't exist.
                return
        else:
            tab.openurl(url)

    @cmdutils.register(instance='mainwindow.tabs.cur', name='reload')
    def reloadpage(self, count=None):
        """Reload the current/[count]th tab.

        Command handler for :reload.

        Args:
            count: The tab index to reload, or None.
        """
        tab = self.tabs.cntwidget(count)
        if tab is not None:
            tab.reload()

    @cmdutils.register(instance='mainwindow.tabs.cur')
    def stop(self, count=None):
        """Stop loading in the current/[count]th tab.

        Command handler for :stop.

        Args:
            count: The tab index to stop, or None.
        """
        tab = self.tabs.cntwidget(count)
        if tab is not None:
            tab.stop()

    @cmdutils.register(instance='mainwindow.tabs.cur', name='print')
    def printpage(self, count=None):
        """Print the current/[count]th tab.

        Command handler for :print.

        Args:
            count: The tab index to print, or None.
        """
        # FIXME that does not what I expect
        tab = self.tabs.cntwidget(count)
        if tab is not None:
            preview = QPrintPreviewDialog(self)
            preview.paintRequested.connect(tab.print)
            preview.exec_()

    @cmdutils.register(instance='mainwindow.tabs.cur')
    def back(self, count=1):
        """Go back in the history of the current tab.

        Command handler for :back.

        Args:
            count: How many pages to go back.
        """
        # FIXME display warning if beginning of history
        for _ in range(count):
            self.tabs.currentWidget().back()

    @cmdutils.register(instance='mainwindow.tabs.cur')
    def forward(self, count=1):
        """Go forward in the history of the current tab.

        Command handler for :forward.

        Args:
            count: How many pages to go forward.
        """
        # FIXME display warning if end of history
        for _ in range(count):
            self.tabs.currentWidget().forward()

    @pyqtSlot(str, int)
    def search(self, text, flags):
        """Search for text in the current page.

        Args:
            text: The text to search for.
            flags: The QWebPage::FindFlags.
        """
        self.tabs.currentWidget().findText(text, flags)

    @cmdutils.register(instance='mainwindow.tabs.cur', hide=True)
    def scroll(self, dx, dy, count=1):
        """Scroll the current tab by count * dx/dy.

        Command handler for :scroll.

        Args:
            dx: How much to scroll in x-direction.
            dy: How much to scroll in x-direction.
            count: multiplier
        """
        dx = int(count) * float(dx)
        dy = int(count) * float(dy)
        self.tabs.currentWidget().page_.mainFrame().scroll(dx, dy)

    @cmdutils.register(instance='mainwindow.tabs.cur', name='scroll_perc_x',
                       hide=True)
    def scroll_percent_x(self, perc=None, count=None):
        """Scroll the current tab to a specific percent of the page (horiz).

        Command handler for :scroll_perc_x.

        Args:
            perc: Percentage to scroll.
            count: Percentage to scroll.
        """
        self._scroll_percent(perc, count, Qt.Horizontal)

    @cmdutils.register(instance='mainwindow.tabs.cur', name='scroll_perc_y',
                       hide=True)
    def scroll_percent_y(self, perc=None, count=None):
        """Scroll the current tab to a specific percent of the page (vert).

        Command handler for :scroll_perc_y

        Args:
            perc: Percentage to scroll.
            count: Percentage to scroll.
        """
        self._scroll_percent(perc, count, Qt.Vertical)

    @cmdutils.register(instance='mainwindow.tabs.cur', hide=True)
    def scroll_page(self, mx, my, count=1):
        """Scroll the frame page-wise.

        Args:
            mx: How many pages to scroll to the right.
            my: How many pages to scroll down.
            count: multiplier
        """
        # FIXME this might not work with HTML frames
        page = self.tabs.currentWidget().page_
        size = page.viewportSize()
        page.mainFrame().scroll(int(count) * float(mx) * size.width(),
                                int(count) * float(my) * size.height())

    @cmdutils.register(instance='mainwindow.tabs.cur')
    def yank(self, sel=False):
        """Yank the current url to the clipboard or primary selection.

        Command handler for :yank.

        Args:
            sel: True to use primary selection, False to use clipboard

        Emit:
            temp_message to display a temporary message.
        """
        clip = QApplication.clipboard()
        url = urlutils.urlstring(self.tabs.currentWidget().url())
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        clip.setText(url, mode)
        self.temp_message.emit('URL yanked to {}'.format(
            'primary selection' if sel else 'clipboard'))

    @cmdutils.register(instance='mainwindow.tabs.cur', name='yanktitle')
    def yank_title(self, sel=False):
        """Yank the current title to the clipboard or primary selection.

        Command handler for :yanktitle.

        Args:
            sel: True to use primary selection, False to use clipboard

        Emit:
            temp_message to display a temporary message.
        """
        clip = QApplication.clipboard()
        title = self.tabs.tabText(self.tabs.currentIndex())
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        clip.setText(title, mode)
        self.temp_message.emit('Title yanked to {}'.format(
            'primary selection' if sel else 'clipboard'))

    @cmdutils.register(instance='mainwindow.tabs.cur', name='zoomin')
    def zoom_in(self, count=1):
        """Zoom in in the current tab.

        Args:
            count: How many steps to take.
        """
        tab = self.tabs.currentWidget()
        tab.zoom(count)

    @cmdutils.register(instance='mainwindow.tabs.cur', name='zoomout')
    def zoom_out(self, count=1):
        """Zoom out in the current tab.

        Args:
            count: How many steps to take.
        """
        tab = self.tabs.currentWidget()
        tab.zoom(-count)
