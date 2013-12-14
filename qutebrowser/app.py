import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout,
    QHBoxLayout, QTabWidget, QWidget, QLabel)
from qutebrowser.widgets import CommandEdit

class TestWindow(QMainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setObjectName(self.__class__.__name__)

        self.cwidget = QWidget(self)
        self.cwidget.setObjectName("cwidget")

        self.vbox = QVBoxLayout(self.cwidget)
        self.vbox.setObjectName("vbox")
        self.setCentralWidget(self.cwidget)

        self.tabs = QTabWidget(self.cwidget)
        self.tabs.setObjectName("tabs")
        self.tab = QWidget()
        self.tab.setObjectName("tab")
        self.tabs.addTab(self.tab, "test")
        self.vbox.addWidget(self.tabs)

        self.status_hbox = QHBoxLayout()

        self.status_cmd = CommandEdit(self.cwidget)
        self.status_cmd.setObjectName("status_cmd")
        self.status_hbox.addWidget(self.status_cmd)

        self.status_lbl = QLabel(self.cwidget)
        self.status_lbl.setObjectName("status_lbl")
        self.status_lbl.setText("Hello World")
        self.status_hbox.addWidget(self.status_lbl)

        self.vbox.addLayout(self.status_hbox)

        #self.retranslateUi(MainWindow)
        #self.tabWidget.setCurrentIndex(0)
        #QtCore.QMetaObject.connectSlotsByName(MainWindow)

        self.show()

def main():
    app = QApplication(sys.argv)
    tw = TestWindow()
    sys.exit(app.exec_())
