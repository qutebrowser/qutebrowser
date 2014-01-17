from PyQt5.QtCore import QObject, pyqtSlot, QUrl
from PyQt5.QtWebKitWidgets import QWebView
from qutebrowser.widgets.tabbar import TabWidget

class TabbedBrowser(TabWidget):
    tabs = []

    def __init__(self, parent):
        super().__init__(parent)
        self.tabopen("http://ddg.gg/")

    @pyqtSlot(str)
    def tabopen(self, url):
        tab = BrowserTab(self)
        tab.openurl(url)
        self.tabs.append(tab)
        self.addTab(tab, url)
        self.setCurrentWidget(tab)

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


class BrowserTab(QWebView):
    def __init__(self, parent):
        super().__init__(parent)
        self.show()

    def openurl(self, url):
        if not url.startswith('http://'):
            url = 'http://' + url
        super().load(QUrl(url))
