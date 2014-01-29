"""Very simple browser for testing purposes."""

import sys

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebKitWidgets import QWebView

app = QApplication(sys.argv)
wv = QWebView()
wv.load(QUrl(sys.argv[1]))
wv.show()
app.exec_()
