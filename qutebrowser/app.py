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

        self.mainwindow.tabs.keypress.connect(self.keyparser.handle)
        self.keyparser.set_cmd_text.connect(self.mainwindow.status.cmd.set_cmd)
        self.mainwindow.status.cmd.got_cmd.connect(self.commandparser.parse)
        self.mainwindow.status.cmd.got_cmd.connect(self.mainwindow.tabs.setFocus)
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
        for cmd in cmds.values():
            cmd.signal.connect(self.cmd_handler)
        self.keyparser.from_cmd_dict(cmdutils.cmd_dict)

    def cmd_handler(self, tpl):
        (count, argv) = tpl
        cmd = argv[0]
        args = argv[1:]

        if cmd == 'open':
            self.mainwindow.tabs.openurl(*args)
        elif cmd == 'tabopen':
            self.mainwindow.tabs.tabopen(*args)
        elif cmd == 'quit':
            QApplication.closeAllWindows() # FIXME
        elif cmd == 'tabclose':
            self.mainwindow.tabs.close_act()
        elif cmd == 'tabprev':
            self.mainwindow.tabs.switch_prev()
        elif cmd == 'tabnext':
            self.mainwindow.tabs.switch_next()
        elif cmd == 'reload':
            self.mainwindow.tabs.reload_act()
        elif cmd == 'stop':
            self.mainwindow.tabs.stop_act()
        elif cmd == 'back':
            self.mainwindow.tabs.back_act()
        elif cmd == 'forward':
            self.mainwindow.tabs.forward_act()
        elif cmd == 'print':
            self.mainwindow.tabs.print_act()
        elif cmd == 'scrolldown':
            self.mainwindow.tabs.scroll_down_act(count=count)
        elif cmd == 'scrollup':
            self.mainwindow.tabs.scroll_up_act(count=count)
        elif cmd == 'scrollleft':
            self.mainwindow.tabs.scroll_left_act(count=count)
        elif cmd == 'scrollright':
            self.mainwindow.tabs.scroll_right_act(count=count)
        elif cmd == 'scrollstart':
            self.mainwindow.tabs.scroll_start_act()
        elif cmd == 'scrollend':
            self.mainwindow.tabs.scroll_end_act()
        elif cmd == 'undo':
            self.mainwindow.tabs.undo_close()
