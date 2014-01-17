from PyQt5.QtCore import QObject, pyqtSlot, QUrl, pyqtSignal
from PyQt5.QtWebKitWidgets import QWebView
from qutebrowser.widgets.tabbar import TabWidget

class TabbedBrowser(TabWidget):
    tabs = []
    cur_progress = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__(parent)
        self.currentChanged.connect(self.index_changed)
        self.tabopen("http://ddg.gg/")

    @pyqtSlot(str)
    def tabopen(self, url):
        tab = BrowserTab(self)
        tab.openurl(url)
        self.tabs.append(tab)
        self.addTab(tab, url)
        self.setCurrentWidget(tab)
        self.progress_changed(tab.progress)
        tab.loadProgress.connect(self.progress_changed)

    @pyqtSlot(str)
    def openurl(self, url):
        tab = self.tabs[self.currentIndex()]
        tab.openurl(url)

    @pyqtSlot()
    def close_act(self):
        if len(self.tabs) > 1:
            idx = self.currentIndex()
            self.tabs.pop(idx)
            self.removeTab(idx)
        else:
            # FIXME
            pass

    @pyqtSlot()
    def switch_prev(self):
        idx = self.currentIndex()
        if idx > 0:
            self.setCurrentIndex(idx - 1)
        else:
            # FIXME
            pass

    @pyqtSlot()
    def switch_next(self):
        idx = self.currentIndex()
        if idx < self.count() - 1:
            self.setCurrentIndex(idx + 1)
        else:
            # FIXME
            pass

    @pyqtSlot(int)
    def progress_changed(self, prog):
        if self.currentWidget() == self.sender():
            self.cur_progress.emit(prog)

    @pyqtSlot(int)
    def index_changed(self, idx):
        tab = self.widget(idx)
        self.cur_progress.emit(tab.progress)

class BrowserTab(QWebView):
    parent = None
    progress = 0

    def __init__(self, parent):
        super().__init__(parent)
        self.loadProgress.connect(self.set_progress)
        self.show()

    def openurl(self, url):
        if not url.startswith('http://'):
            url = 'http://' + url
        super().load(QUrl(url))

    def set_progress(self, prog):
        self.progress = prog
