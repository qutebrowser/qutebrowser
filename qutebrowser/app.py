""" Initialization of qutebrowser and application-wide things """

import sys
import logging
import faulthandler
from signal import signal, SIGINT
from argparse import ArgumentParser

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QUrl, QTimer

import qutebrowser.commands.utils as cmdutils
import qutebrowser.utils.config as config
from qutebrowser.widgets.mainwindow import MainWindow
from qutebrowser.commands.keys import KeyParser
from qutebrowser.utils.appdirs import AppDirs


class QuteBrowser(QApplication):
    """Main object for qutebrowser.

    Can be used like this:

    >>> app = QuteBrowser()
    >>> sys.exit(app.exec_())
    """
    dirs = None  # AppDirs - config/cache directories
    config = None  # Config(Parser) object
    mainwindow = None
    commandparser = None
    keyparser = None
    args = None  # ArgumentParser
    timer = None  # QTimer for python hacks

    def __init__(self):
        super().__init__(sys.argv)
        # Exit on exceptions
        sys.excepthook = self._tmp_exception_hook

        # Handle segfaults
        faulthandler.enable()

        self._parseopts()
        self._initlog()

        self.dirs = AppDirs('qutebrowser')
        if self.args.confdir is None:
            confdir = self.dirs.user_config_dir
        elif self.args.confdir == '':
            confdir = None
        else:
            confdir = self.args.confdir
        config.init(confdir)

        self.commandparser = cmdutils.CommandParser()
        self.keyparser = KeyParser(self.mainwindow)
        self._init_cmds()
        self.mainwindow = MainWindow()

        self.aboutToQuit.connect(config.config.save)
        self.mainwindow.tabs.keypress.connect(self.keyparser.handle)
        self.keyparser.set_cmd_text.connect(self.mainwindow.status.cmd.set_cmd)
        self.mainwindow.status.cmd.got_cmd.connect(self.commandparser.run)
        self.mainwindow.status.cmd.got_cmd.connect(
            self.mainwindow.tabs.setFocus)
        self.commandparser.error.connect(self.mainwindow.status.disp_error)
        self.keyparser.commandparser.error.connect(
            self.mainwindow.status.disp_error)
        self.keyparser.keystring_updated.connect(
            self.mainwindow.status.txt.set_keystring)

        self.mainwindow.show()
        self._python_hacks()

    def _tmp_exception_hook(self, exctype, value, traceback):
        """Handle exceptions while initializing by simply exiting.

        This is only temporary and will get replaced by exception_hook later.
        It's necessary because PyQt seems to ignore exceptions by default.
        """
        sys.__excepthook__(exctype, value, traceback)
        self.exit(1)

    def _exception_hook(self, exctype, value, traceback):
        """Handle uncaught python exceptions.

        It'll try very hard to write all open tabs to a file, and then exit
        gracefully.
        """
        # pylint: disable=broad-except
        sys.__excepthook__(exctype, value, traceback)
        try:
            for tabidx in range(self.mainwindow.tabs.count()):
                try:
                    # FIXME write to some file
                    print(self.mainwindow.tabs.widget(tabidx).url().url())
                except Exception:
                    pass
        except Exception:
            pass
        self.exit(1)

    def _python_hacks(self):
        """Get around some PyQt-oddities by evil hacks.

        This sets up the uncaught exception hook, quits with an appropriate
        exit status, and handles Ctrl+C properly by passing control to the
        Python interpreter once all 500ms.
        """
        sys.excepthook = self._exception_hook
        signal(SIGINT, lambda *args: self.exit(128 + SIGINT))
        self.timer = QTimer()
        self.timer.start(500)
        self.timer.timeout.connect(lambda: None)

    def _parseopts(self):
        """Parse command line options."""
        parser = ArgumentParser("usage: %(prog)s [options]")
        parser.add_argument('-l', '--log', dest='loglevel',
                            help='Set loglevel', default='info')
        parser.add_argument('-c', '--confdir', help='Set config directory '
                            '(empty for no config storage)')
        self.args = parser.parse_args()

    def _initlog(self):
        """Initialisation of the logging output."""
        loglevel = self.args.loglevel
        numeric_level = getattr(logging, loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: {}'.format(loglevel))
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s [%(levelname)s] '
                   '[%(module)s:%(funcName)s:%(lineno)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')

    def _init_cmds(self):
        """Initialisation of the qutebrowser commands.

        Registers all commands, connects its signals, and sets up keyparser.
        """
        cmdutils.register_all()
        for cmd in cmdutils.cmd_dict.values():
            cmd.signal.connect(self.cmd_handler)
        try:
            self.keyparser.from_config_sect(config.config['keybind'])
        except KeyError:
            pass

    def cmd_handler(self, tpl):
        """Handle commands and delegate the specific actions.

        This gets called as a slot from all commands, and then calls the
        appropriate command handler.

        tpl -- A tuple in the form (count, argv) where argv is [cmd, arg, ...]

        All handlers supporting a count should have a keyword argument count.
        """
        (count, argv) = tpl
        cmd = argv[0]
        args = argv[1:]

        handlers = {
            'open':          self.mainwindow.tabs.openurl,
            'tabopen':       self.mainwindow.tabs.tabopen,
            'quit':          self.quit,
            'tabclose':      self.mainwindow.tabs.cur_close,
            'tabprev':       self.mainwindow.tabs.switch_prev,
            'tabnext':       self.mainwindow.tabs.switch_next,
            'reload':        self.mainwindow.tabs.cur_reload,
            'stop':          self.mainwindow.tabs.cur_stop,
            'back':          self.mainwindow.tabs.cur_back,
            'forward':       self.mainwindow.tabs.cur_forward,
            'print':         self.mainwindow.tabs.cur_print,
            'scroll':        self.mainwindow.tabs.cur_scroll,
            'scroll_perc_x': self.mainwindow.tabs.cur_scroll_percent_x,
            'scroll_perc_y': self.mainwindow.tabs.cur_scroll_percent_y,
            'undo':          self.mainwindow.tabs.undo_close,
            'pyeval':        self.pyeval,
        }

        handler = handlers[cmd]

        if self.sender().count:
            return handler(*args, count=count)
        else:
            return handler(*args)

    def pyeval(self, s):
        """Evaluate a python string and display the results as a webpage.

        s -- The string to evaluate.

        :pyeval command handler.
        """
        try:
            r = eval(s)
            out = repr(r)
        except Exception as e:  # pylint: disable=broad-except
            out = ': '.join([e.__class__.__name__, str(e)])

        # FIXME we probably want some nicer interface to display these about:
        # pages
        tab = self.mainwindow.tabs.currentWidget()
        tab.setUrl(QUrl('about:pyeval'))
        tab.setContent(out.encode('UTF-8'), 'text/plain')
