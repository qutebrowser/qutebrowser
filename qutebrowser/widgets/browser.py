import logging

from PyQt5.QtCore import QUrl, pyqtSignal, Qt, QPoint, QEvent
from PyQt5.QtPrintSupport import QPrintPreviewDialog
from PyQt5.QtWebKitWidgets import QWebView, QWebPage

import qutebrowser.utils as utils
from qutebrowser.widgets.tabbar import TabWidget

class TabbedBrowser(TabWidget):
    """A TabWidget with QWebViews inside"""

    cur_progress = pyqtSignal(int) # Progress of the current tab changed
    cur_load_started = pyqtSignal() # Current tab started loading
    cur_load_finished = pyqtSignal(bool) # Current tab finished loading
    cur_statusbar_message = pyqtSignal(str) # Status bar message
    # FIXME we need to store this in our browser object
    # Current tab changed scroll position
    cur_scroll_perc_changed = pyqtSignal(int, int)
    keypress = pyqtSignal('QKeyEvent')
    _url_stack = [] # Stack of URLs of closed tabs

    def __init__(self, parent):
        super().__init__(parent)
        self.currentChanged.connect(self._currentChanged_handler)
        self.tabopen(QUrl("http://ddg.gg/"))

    def tabopen(self, url):
        """Opens a new tab with a given url"""
        url = utils.qurl(url)
        tab = BrowserTab(self)
        tab.openurl(url)
        self.addTab(tab, url.url())
        self.setCurrentWidget(tab)
        self.cur_progress.emit(tab.progress)
        tab.loadProgress.connect(
            lambda *args: self._filter_signals(self.cur_progress, *args))
        tab.loadFinished.connect(
            lambda *args: self._filter_signals(self.cur_load_finished, *args))
        tab.loadStarted.connect(
            lambda *args: self._filter_signals(self.cur_load_started, *args))
        # FIXME does QtWebView even do something sensible with that signal?
        tab.statusBarMessage.connect(
            lambda *args: self._filter_signals(self.cur_statusbar_message, *args))
        tab.scroll_pos_changed.connect(self._scroll_pos_changed_handler)
        # FIXME should we really bind this to loadStarted? Sometimes the URL
        # isn't set correctly at this point, e.g. when doing
        # setContent(..., baseUrl=QUrl('foo'))
        tab.loadStarted.connect(self._loadStarted_handler)
        tab.titleChanged.connect(self._titleChanged_handler)
        # FIXME sometimes this doesn't load
        tab.open_tab.connect(self.tabopen)

    def openurl(self, url):
        """Opens an url in the current tab"""
        self.currentWidget().openurl(url)

    def undo_close(self):
        """Undos closing a tab"""
        if self._url_stack:
            self.tabopen(self._url_stack.pop())

    def cur_close(self):
        """Closes the current tab"""
        if self.count() > 1:
            idx = self.currentIndex()
            tab = self.currentWidget()
            # FIXME maybe we actually should store the webview objects here
            self._url_stack.append(tab.url())
            self.removeTab(idx)
        else:
            # FIXME
            pass

    def cur_reload(self):
        """Reloads the current tab"""
        self.currentWidget().reload()

    def cur_stop(self):
        """Stops loading in the current tab"""
        self.currentWidget().stop()

    def cur_print(self):
        """Prints the current tab"""
        # FIXME that does not what I expect
        preview = QPrintPreviewDialog()
        preview.paintRequested.connect(self.currentWidget().print)
        preview.exec_()

    def cur_back(self):
        """Goes back in the history of the current tab"""
        # FIXME display warning if beginning of history
        self.currentWidget().back()

    def cur_forward(self):
        """Goes forward in the history of the current tab"""
        # FIXME display warning if end of history
        self.currentWidget().forward()

    def cur_scroll(self, dx, dy, count=None):
        """Scrolls the current tab by count * dx/dy"""
        if count is None:
            count = 1
        dx = int(count) * int(dx)
        dy = int(count) * int(dy)
        self.currentWidget().page().mainFrame().scroll(dx, dy)

    def cur_scroll_percent_x(self, perc=None, count=None):
        """Scrolls the current tab to a specific percent of the page.
        Accepts percentage either as argument, or as count.
        """
        self._cur_scroll_percent(perc, count, Qt.Horizontal)

    def cur_scroll_percent_y(self, perc=None, count=None):
        """Scrolls the current tab to a specific percent of the page
        Accepts percentage either as argument, or as count.
        """
        self._cur_scroll_percent(perc, count, Qt.Vertical)

    def _cur_scroll_percent(self, perc=None, count=None, orientation=None):
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

    def switch_prev(self):
        """Switches to the previous tab"""
        idx = self.currentIndex()
        if idx > 0:
            self.setCurrentIndex(idx - 1)
        else:
            # FIXME
            pass

    def switch_next(self):
        """Switches to the next tab"""
        idx = self.currentIndex()
        if idx < self.count() - 1:
            self.setCurrentIndex(idx + 1)
        else:
            # FIXME
            pass

    def keyPressEvent(self, e):
        self.keypress.emit(e)
        super().keyPressEvent(e)

    def _titleChanged_handler(self, text):
        if text:
            self.setTabText(self.indexOf(self.sender()), text)

    def _loadStarted_handler(self):
        s = self.sender()
        self.setTabText(self.indexOf(s), s.url().toString())

    def _filter_signals(self, signal, *args):
        """Filters signals, and triggers TabbedBrowser signals if the signal
        was sent from the _current_ tab and not from any other one.
        """
        dbgstr = "{} ({})".format(
            signal.signal, ','.join([str(e) for e in args]))
        if self.currentWidget() == self.sender():
            logging.debug('{} - emitting'.format(dbgstr))
            signal.emit(*args)
        else:
            logging.debug('{} - ignoring'.format(dbgstr))

    def _currentChanged_handler(self, idx):
        tab = self.widget(idx)
        self.cur_progress.emit(tab.progress)

    def _scroll_pos_changed_handler(self, x, y):
        """Gets the new position from a BrowserTab. If it's the current tab, it
        calculates the percentage and emits cur_scroll_perc_changed.
        """
        sender = self.sender()
        if sender != self.currentWidget():
            return
        frame = sender.page().mainFrame()
        m = (frame.scrollBarMaximum(Qt.Horizontal),
             frame.scrollBarMaximum(Qt.Vertical))
        perc = (round(100 * x / m[0]) if m[0] != 0 else 0,
                round(100 * y / m[1]) if m[1] != 0 else 0)
        self.cur_scroll_perc_changed.emit(*perc)

class BrowserTab(QWebView):
    """One browser tab in TabbedBrowser"""
    progress = 0
    scroll_pos_changed = pyqtSignal(int, int)
    _scroll_pos = (-1, -1)
    midbutton = False # if the middle button was pressed
    open_tab = pyqtSignal('QUrl')

    def __init__(self, parent):
        super().__init__(parent)
        self.loadProgress.connect(self.set_progress)
        self.page().setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        self.installEventFilter(self)
        self.linkClicked.connect(self.link_handler)
        # FIXME find some way to hide scrollbars without setScrollBarPolicy
        self.show()

    def openurl(self, url):
        """Opens an URL in the browser"""
        return self.load(utils.qurl(url))

    def link_handler(self, url):
        if self.midbutton:
            self.open_tab.emit(url)
        else:
            self.openurl(url)

    def set_progress(self, prog):
        self.progress = prog

    def eventFilter(self, watched, e):
        """Dirty hack to emit a signal if the scroll position changed.

        We listen to repaint requests here, in the hope a repaint will always
        be requested when scrolling, and if the scroll position actually
        changed, we emit a signal.
        """
        if watched == self and e.type() == QEvent.Paint:
            frame = self.page().mainFrame()
            new_pos = (frame.scrollBarValue(Qt.Horizontal),
                       frame.scrollBarValue(Qt.Vertical))
            if self._scroll_pos != new_pos:
                logging.debug("Updating scroll position")
                self.scroll_pos_changed.emit(*new_pos)
            self._scroll_pos = new_pos
        return super().eventFilter(watched, e)

    def event(self, e):
        """Another hack to see when a link was pressed with the middle
        button
        """
        if e.type() in [QEvent.MouseButtonPress, QEvent.MouseButtonDblClick]:
            self.midbutton = (e.button() == Qt.MidButton)
        return super().event(e)
