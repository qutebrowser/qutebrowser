import sys
from PyQt5.QtWidgets import QWidget, QApplication
from qutebrowser.widgets.mainwindow import MainWindow
import qutebrowser.commands as cmds

def main():
    app = QApplication(sys.argv)

    mw = MainWindow()
    cp = cmds.CommandParser()
    mw.status.cmd.returnPressed.connect(lambda: cp.parse(mw.status.cmd.text()))
    cmds.cmd_dict['openurl'].connect(mw.tabs.openurl)
    cmds.cmd_dict['tabopen'].connect(mw.tabs.tabopen)
    mw.show()

    sys.exit(app.exec_())
