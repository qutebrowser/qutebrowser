import sys
import argparse
import logging
from PyQt5.QtWidgets import QWidget, QApplication
from qutebrowser.widgets.mainwindow import MainWindow
from qutebrowser.commands.keys import KeyParser
import qutebrowser.commands.utils as cmdutils

class QuteBrowser(QApplication):
    def __init__(self):
        super().__init__(sys.argv)
        args = self.parseopts()
        self.initlog()

        self.mainwindow = MainWindow()
        self.commandparser = cmdutils.CommandParser()
        self.keyparser = KeyParser(self.mainwindow)

        self.keyparser.set_cmd_text.connect(self.mainwindow.status.cmd.set_cmd)
        self.mainwindow.status.cmd.got_cmd.connect(self.commandparser.parse)
        self.mainwindow.status.cmd.got_cmd.connect(self.mainwindow.setFocus)
        self.commandparser.error.connect(self.mainwindow.status.disp_error)

        self.init_cmds()
        self.mainwindow.show()

    def parseopts(self):
        parser = argparse.ArgumentParser("usage: %(prog)s [options]")
        parser.add_argument('-l', '--log', dest='loglevel',
                            help='Set loglevel', default=0)
        self.args = parser.parse_args()

    def initlog(self):
        """ Initialisation of the log """
        if self.args.loglevel:
            loglevel = self.args.loglevel
        else:
            loglevel = 'info'
        numeric_level = getattr(logging, loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % loglevel)
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s [%(levelname)s] '
                   '[%(module)s:%(funcName)s:%(lineno)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')

    def init_cmds(self):
        cmdutils.register_all()
        cmds = cmdutils.cmd_dict
        cmds['open'].signal.connect(self.mainwindow.tabs.openurl)
        cmds['tabopen'].signal.connect(self.mainwindow.tabs.tabopen)
        cmds['quit'].signal.connect(QApplication.closeAllWindows) # FIXME
        cmds['tabclose'].signal.connect(self.mainwindow.tabs.close_act)
        cmds['tabprev'].signal.connect(self.mainwindow.tabs.switch_prev)
        cmds['tabnext'].signal.connect(self.mainwindow.tabs.switch_next)
        cmds['reload'].signal.connect(self.mainwindow.tabs.reload_act)
        cmds['stop'].signal.connect(self.mainwindow.tabs.stop_act)
        cmds['back'].signal.connect(self.mainwindow.tabs.back_act)
        cmds['forward'].signal.connect(self.mainwindow.tabs.forward_act)
        cmds['print'].signal.connect(self.mainwindow.tabs.print_act)
        cmds['scrolldown'].signal.connect(self.mainwindow.tabs.scroll_down_act)
        cmds['scrollup'].signal.connect(self.mainwindow.tabs.scroll_up_act)
        cmds['scrollleft'].signal.connect(self.mainwindow.tabs.scroll_left_act)
        cmds['scrollright'].signal.connect(
                self.mainwindow.tabs.scroll_right_act)
        cmds['scrollstart'].signal.connect(
                self.mainwindow.tabs.scroll_start_act)
        cmds['scrollend'].signal.connect(
                self.mainwindow.tabs.scroll_end_act)
        cmds['undo'].signal.connect(self.mainwindow.tabs.undo_close)
        self.keyparser.from_cmd_dict(cmdutils.cmd_dict)
