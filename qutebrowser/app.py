import sys
import argparse
import logging
from PyQt5.QtWidgets import QWidget, QApplication
from qutebrowser.widgets.mainwindow import MainWindow
from qutebrowser.commands.keys import KeyParser
import qutebrowser.commands.utils as cmdutils

def parseopts():
    parser = argparse.ArgumentParser("usage: %(prog)s [options]")
    parser.add_argument('-l', '--log', dest='loglevel', help='Set loglevel',
                        default=0)
    args = parser.parse_args()
    return args

def initlog(args):
    """ Initialisation of the log """
    if (args.loglevel):
        loglevel = args.loglevel
    else:
        loglevel = 'info'
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s [%(levelname)s] [%(module)s:%(funcName)s:%(lineno)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

def main():
    args = parseopts()
    initlog(args)

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
    cmds['reload'].signal.connect(mw.tabs.reload_act)
    cmds['stop'].signal.connect(mw.tabs.stop_act)
    cmds['back'].signal.connect(mw.tabs.back_act)
    cmds['forward'].signal.connect(mw.tabs.forward_act)
    cmds['print'].signal.connect(mw.tabs.print_act)
    cmds['scrolldown'].signal.connect(mw.tabs.scroll_down_act)
    cmds['scrollup'].signal.connect(mw.tabs.scroll_up_act)
    cmds['scrollleft'].signal.connect(mw.tabs.scroll_left_act)
    cmds['scrollright'].signal.connect(mw.tabs.scroll_right_act)
    cmds['undo'].signal.connect(mw.tabs.undo_close)
    kp.from_cmd_dict(cmds)

    mw.show()
    sys.exit(app.exec_())
