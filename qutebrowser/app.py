import sys
from PyQt5.QtWidgets import QWidget, QApplication
from qutebrowser.widgets.mainwindow import MainWindow
import qutebrowser.commands as cmds

def main():
    app = QApplication(sys.argv)

    mw = MainWindow()
    cp = cmds.CommandParser()
    mw.status.cmd.got_cmd.connect(cp.parse)
    mw.status.cmd.got_cmd.connect(mw.setFocus)
    cmds.cmd_dict['open'].signal.connect(mw.tabs.openurl)
    cmds.cmd_dict['tabopen'].signal.connect(mw.tabs.tabopen)
    cmds.cmd_dict['quit'].signal.connect(QApplication.closeAllWindows) # FIXME
    mw.show()

    sys.exit(app.exec_())
