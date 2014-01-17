import sys
from PyQt5.QtWidgets import QWidget, QApplication
from qutebrowser.widgets.mainwindow import MainWindow
from qutebrowser.commands.keys import KeyParser
import qutebrowser.commands.utils as cmdutils

def main():
    app = QApplication(sys.argv)

    mw = MainWindow()
    cp = cmdutils.CommandParser()
    kp = KeyParser(mw)
    kp.set_cmd_text.connect(mw.status.cmd.set_cmd)
    mw.status.cmd.got_cmd.connect(cp.parse)
    mw.status.cmd.got_cmd.connect(mw.setFocus)
    cp.error.connect(mw.status.disp_error)

    cmdutils.register_all()
    cmds = cmdutils.cmd_dict
    cmds['open'].signal.connect(mw.tabs.openurl)
    cmds['tabopen'].signal.connect(mw.tabs.tabopen)
    cmds['quit'].signal.connect(QApplication.closeAllWindows) # FIXME
    cmds['tabclose'].signal.connect(mw.tabs.close_act)
    cmds['tabprev'].signal.connect(mw.tabs.switch_prev)
    cmds['tabnext'].signal.connect(mw.tabs.switch_next)
    kp.from_cmd_dict(cmds)

    mw.show()
    sys.exit(app.exec_())
