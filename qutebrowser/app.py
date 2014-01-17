import sys
from PyQt5.QtWidgets import QWidget, QApplication
from qutebrowser.widgets.mainwindow import MainWindow
from qutebrowser.keys import KeyParser
import qutebrowser.commands as cmds

def main():
    app = QApplication(sys.argv)

    mw = MainWindow()
    cp = cmds.CommandParser()
    kp = KeyParser()
    kp.set_cmd_text.connect(mw.status.cmd.set_cmd)
    mw.status.cmd.got_cmd.connect(cp.parse)
    mw.status.cmd.got_cmd.connect(mw.setFocus)
    cmds.cmd_dict['open'].signal.connect(mw.tabs.openurl)
    cmds.cmd_dict['tabopen'].signal.connect(mw.tabs.tabopen)
    cmds.cmd_dict['quit'].signal.connect(QApplication.closeAllWindows) # FIXME
    kp.from_cmd_dict(cmds.cmd_dict, mw.tabs)
    mw.show()

    sys.exit(app.exec_())
