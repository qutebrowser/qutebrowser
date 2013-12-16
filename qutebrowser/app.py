import sys
from PyQt5.QtWidgets import QWidget, QApplication
from qutebrowser.widgets.mainwindow import MainWindow
from qutebrowser.commands import CommandParser

def main():
    app = QApplication(sys.argv)

    mw = MainWindow()
    cp = CommandParser()
    mw.status.cmd.returnPressed.connect(lambda: cp.parse(mw.status.cmd.text()))
    cp.openurl.connect(mw.tabs.openurl)
    cp.tabopen.connect(mw.tabs.tabopen)
    mw.show()

    sys.exit(app.exec_())
