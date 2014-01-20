import logging

from PyQt5.QtCore import QUrl, pyqtSignal, Qt, QPoint
from PyQt5.QtPrintSupport import QPrintPreviewDialog
from PyQt5.QtWebKitWidgets import QWebView

from qutebrowser.widgets.tabbar import TabWidget

class TabbedBrowser(TabWidget):
    """A TabWidget with QWebViews inside"""

    cur_progress = pyqtSignal(int) # Progress of the current tab changed
    cur_load_finished = pyqtSignal(bool) # Current tab finished loading
    keypress = pyqtSignal('QKeyEvent')
    _url_stack = [] # Stack of URLs of closed tabs

    def __init__(self, parent):
        super().__init__(parent)
        self.currentChanged.connect(self._currentChanged_handler)
        self.tabopen("http://ddg.gg/")

    def tabopen(self, url):
        """Opens a new tab with a given url"""
        tab = BrowserTab(self)
        tab.openurl(url)
        self.addTab(tab, url)
        self.setCurrentWidget(tab)
        self.cur_progress.emit(tab.progress)
        tab.loadProgress.connect(
            lambda *args: self._filter_signals(self.cur_progress, *args))
        tab.loadFinished.connect(
            lambda *args: self._filter_signals(self.cur_load_finished, *args))
        # FIXME should we really bind this to loadStarted? Sometimes the URL
        # isn't set correctly at this point, e.g. when doing
        # setContent(..., baseUrl=QUrl('foo'))
        tab.loadStarted.connect(self._loadStarted_handler)
        tab.titleChanged.connect(self._titleChanged_handler)

    def openurl(self, url):
        """Opens an url in the current tab"""
        tab = self.currentWidget()
        tab.openurl(url)

    def undo_close(self):
        """Undos closing a tab"""
        if self._url_stack:
            self.tabopen(self._url_stack.pop())

    def cur_close(self):
        """Closes the current tab"""
        if self.count() > 1:
            idx = self.currentIndex()
            tab = self.currentWidget()
            # FIXME maybe we should add the QUrl object here and deal with QUrls everywhere
            # FIXME maybe we actually should store the webview objects here
            self._url_stack.append(tab.url().url())
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

    def cur_scroll_down(self, count=None):
        """Scrolls the current tab down"""
        if count is None:
            count = 50
        self.currentWidget().page().mainFrame().scroll(0, count)

    def cur_scroll_up(self, count=None):
        """Scrolls the current tab up"""
        if count is None:
            count = 50
        self.currentWidget().page().mainFrame().scroll(0, -count)

    def cur_scroll_left(self, count=None):
        """Scrolls the current tab left"""
        if count is None:
            count = 50
        self.currentWidget().page().mainFrame().scroll(-count, 0)

    def cur_scroll_right(self, count=None):
        """Scrolls the current tab right"""
        if count is None:
            count = 50
        self.currentWidget().page().mainFrame().scroll(count, 0)

    def cur_scroll_start(self):
        """Scrolls the current tab to the beginning"""
        frame = self.currentWidget().page().mainFrame()
        cur_pos = frame.scrollPosition()
        frame.setScrollPosition(QPoint(cur_pos.x(), 0))

    def cur_scroll_end(self):
        """Scrolls the current tab to the end"""
        frame = self.currentWidget().page().mainFrame()
        cur_pos = frame.scrollPosition()
        size = frame.contentsSize()
        frame.setScrollPosition(QPoint(cur_pos.x(), size.height()))

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

class BrowserTab(QWebView):
    """One browser tab in TabbedBrowser"""
    progress = 0

    def __init__(self, parent):
        super().__init__(parent)
        frame = self.page().mainFrame()
        frame.setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)
        frame.setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        self.loadProgress.connect(self.set_progress)
        self.show()

    def openurl(self, url):
        """Opens an URL in the browser"""
        if not url.startswith('http://'):
            url = 'http://' + url
        self.load(QUrl(url))

    def set_progress(self, prog):
        self.progress = prog
