import sys
from PyQt5.QtWidgets import QWidget, QApplication
from qutebrowser.widgets.mainwindow import MainWindow

def main():
    app = QApplication(sys.argv)
    mw = MainWindow()

    tab = QWidget()
    tab2 = QWidget()
    tab.setObjectName("tab")
    tab2.setObjectName("tab2")
    mw.tabs.addTab(tab, "test")
    mw.tabs.addTab(tab2, "test2")
    mw.show()

    sys.exit(app.exec_())
