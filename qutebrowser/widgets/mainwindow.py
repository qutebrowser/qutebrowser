from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget)
from qutebrowser.widgets.statusbar import StatusBar
from qutebrowser.widgets.browser import TabbedBrowser

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName(self.__class__.__name__)

        self.cwidget = QWidget(self)
        self.cwidget.setObjectName("cwidget")
        self.setCentralWidget(self.cwidget)

        self.vbox = QVBoxLayout(self.cwidget)
        self.vbox.setObjectName("vbox")
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(0)

        self.tabs = TabbedBrowser(self)
        self.tabs.setObjectName("tabs")
        self.vbox.addWidget(self.tabs)

        self.status = StatusBar(self)
        self.vbox.addWidget(self.status)

        self.tabs.cur_progress.connect(self.status.prog.set_progress)
        self.tabs.cur_load_finished.connect(self.status.prog.load_finished)
        self.status.cmd.esc_pressed.connect(self.tabs.setFocus)

        #self.retranslateUi(MainWindow)
        #self.tabWidget.setCurrentIndex(0)
        #QtCore.QMetaObject.connectSlotsByName(MainWindow)
