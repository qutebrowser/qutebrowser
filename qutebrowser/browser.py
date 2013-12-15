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

class BrowserTab(QWebView):
    def __init__(self, parent):
        super().__init__(parent)
        self.show()

    def openurl(self, url):
        if not url.startswith('http://'):
            url = 'http://' + url
        super().load(QUrl(url))
