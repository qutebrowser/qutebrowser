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

        handlers = {
            'open': self.mainwindow.tabs.openurl,
            'tabopen': self.mainwindow.tabs.tabopen,
            'quit': QApplication.closeAllWindows, # FIXME
            'tabclose': self.mainwindow.tabs.close_act,
            'tabprev': self.mainwindow.tabs.switch_prev,
            'tabnext': self.mainwindow.tabs.switch_next,
            'reload': self.mainwindow.tabs.reload_act,
            'stop': self.mainwindow.tabs.stop_act,
            'back': self.mainwindow.tabs.back_act,
            'forward': self.mainwindow.tabs.forward_act,
            'print': self.mainwindow.tabs.print_act,
            'scrolldown': self.mainwindow.tabs.scroll_down_act,
            'scrollup': self.mainwindow.tabs.scroll_up_act,
            'scrollleft': self.mainwindow.tabs.scroll_left_act,
            'scrollright': self.mainwindow.tabs.scroll_right_act,
            'scrollstart': self.mainwindow.tabs.scroll_start_act,
            'scrollend': self.mainwindow.tabs.scroll_end_act,
            'undo': self.mainwindow.tabs.undo_close,
            'pyeval': self.pyeval
        }

        handler = handlers[cmd]
        sender = self.sender()

        if sender.count:
            handler(*args, count=count)
        else:
            handler(*args)

    def pyeval(self, s):
        try:
            r = eval(s)
            out = repr(r)
        except Exception as e:
            out = ': '.join([e.__class__.__name__, str(e)])

        tab = self.mainwindow.tabs.currentWidget()
        tab.setContent(out.encode('UTF-8'), 'text/plain')

