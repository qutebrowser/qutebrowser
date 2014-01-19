from PyQt5.QtCore import QObject, pyqtSlot, QUrl, pyqtSignal, Qt, QPoint
from PyQt5.QtPrintSupport import QPrintPreviewDialog
from PyQt5.QtWebKitWidgets import QWebView
from qutebrowser.widgets.tabbar import TabWidget
import logging

class TabbedBrowser(TabWidget):
    cur_progress = pyqtSignal(int)
    cur_load_finished = pyqtSignal(bool)
    keypress = pyqtSignal('QKeyEvent')
    url_stack = []

    def __init__(self, parent):
        super().__init__(parent)
        self.currentChanged.connect(self.index_changed)
        self.tabopen("http://ddg.gg/")

    def tabopen(self, url):
        tab = BrowserTab(self)
        tab.openurl(url)
        self.addTab(tab, url)
        self.setCurrentWidget(tab)
        self.progress_changed(tab.progress)
        tab.loadProgress.connect(self.progress_changed)
        tab.loadFinished.connect(self.load_finished)
        tab.titleChanged.connect(self.update_title)

    def openurl(self, url):
        tab = self.currentWidget()
        tab.openurl(url)

    def undo_close(self):
        if self.url_stack:
            self.tabopen(self.url_stack.pop())

    def close_act(self):
        if self.count() > 1:
            idx = self.currentIndex()
            tab = self.currentWidget()
            # FIXME maybe we should add the QUrl object here and deal with QUrls everywhere
            # FIXME maybe we actually should store the webview objects here
            self.url_stack.append(tab.url().url())
            self.removeTab(idx)
        else:
            # FIXME
            pass

    def reload_act(self):
        self.currentWidget().reload()

    def stop_act(self):
        self.currentWidget().stop()

    def print_act(self):
        # FIXME that does not what I expect
        preview = QPrintPreviewDialog()
        preview.paintRequested.connect(self.currentWidget().print)
        preview.exec_()

    def back_act(self):
        # FIXME display warning if beginning of history
        self.currentWidget().back()

    def forward_act(self):
        # FIXME display warning if end of history
        self.currentWidget().forward()

    def scroll_down_act(self, count=50):
        self.currentWidget().page().mainFrame().scroll(0, count)

    def scroll_up_act(self, count=50):
        self.currentWidget().page().mainFrame().scroll(0, -count)

    def scroll_left_act(self, count=50):
        self.currentWidget().page().mainFrame().scroll(-count, 0)

    def scroll_right_act(self, count=50):
        self.currentWidget().page().mainFrame().scroll(count, 0)

    def scroll_start_act(self):
        frame = self.currentWidget().page().mainFrame()
        cur_pos = frame.scrollPosition()
        frame.setScrollPosition(QPoint(cur_pos.x(), 0))

    def scroll_end_act(self):
        frame = self.currentWidget().page().mainFrame()
        cur_pos = frame.scrollPosition()
        size = frame.contentsSize()
        frame.setScrollPosition(QPoint(cur_pos.x(), size.height()))

    def switch_prev(self):
        idx = self.currentIndex()
        if idx > 0:
            self.setCurrentIndex(idx - 1)
        else:
            # FIXME
            pass

    def switch_next(self):
        idx = self.currentIndex()
        if idx < self.count() - 1:
            self.setCurrentIndex(idx + 1)
        else:
            # FIXME
            pass

    def progress_changed(self, prog):
        self.filter_signals(self.cur_progress, prog)

    def load_finished(self, ok):
        self.filter_signals(self.cur_load_finished, ok)

    def update_title(self, text):
        if text:
            self.setTabText(self.indexOf(self.sender()), text)

    def filter_signals(self, signal, *args):
        dbgstr = "{} ({})".format(
            signal.signal, ','.join([str(e) for e in args]))
        if self.currentWidget() == self.sender():
            logging.debug('{} - emitting'.format(dbgstr))
            signal.emit(*args)
        else:
            logging.debug('{} - ignoring'.format(dbgstr))

    def index_changed(self, idx):
        tab = self.widget(idx)
        self.cur_progress.emit(tab.progress)

    def keyPressEvent(self, e):
        self.keypress.emit(e)
        super().keyPressEvent(e)

class BrowserTab(QWebView):
    parent = None
    progress = 0

    def __init__(self, parent):
        super().__init__(parent)
        frame = self.page().mainFrame()
        frame.setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)
        frame.setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        self.loadProgress.connect(self.set_progress)
        self.show()

    def openurl(self, url):
        if not url.startswith('http://'):
            url = 'http://' + url
        super().load(QUrl(url))

    def set_progress(self, prog):
        self.progress = prog
