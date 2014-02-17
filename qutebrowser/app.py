# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Initialization of qutebrowser and application-wide things."""

import os
import sys
import logging
import functools
import subprocess
from signal import signal, SIGINT
from argparse import ArgumentParser

# Print a nice traceback on segfault -- only available on Python 3.3+, but if
# it's unavailable, it doesn't matter much.
try:
    import faulthandler
except ImportError:
    pass
else:
    faulthandler.enable()

# This is a really odd place to do this, but we have to do this before
# importing PyQt or it won't work.
# See https://bugreports.qt-project.org/browse/QTBUG-36099
import qutebrowser.utils.harfbuzz as harfbuzz
harfbuzz.fix()

from PyQt5.QtWidgets import QApplication, QDialog
from PyQt5.QtCore import pyqtSlot, QTimer, QEventLoop

import qutebrowser
import qutebrowser.commands.utils as cmdutils
import qutebrowser.utils.config as config
import qutebrowser.utils.about as about
from qutebrowser.widgets.mainwindow import MainWindow
from qutebrowser.widgets.crash import CrashDialog
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
    timers = None
    shutting_down = False
    _quit_status = None

    def __init__(self):
        super().__init__(sys.argv)
        self._quit_status = {}
        sys.excepthook = self._exception_hook

        self._parseopts()
        self._initlog()
        self._initmisc()

        self.dirs = AppDirs('qutebrowser')
        if self.args.confdir is None:
            confdir = self.dirs.user_config_dir
        elif self.args.confdir == '':
            confdir = None
        else:
            confdir = self.args.confdir
        config.init(confdir)

        self.commandparser = cmdutils.CommandParser()
        self.searchparser = cmdutils.SearchParser()
        self.keyparser = KeyParser(self.mainwindow)
        self._init_cmds()
        self.mainwindow = MainWindow()

        self.setQuitOnLastWindowClosed(False)
        self.lastWindowClosed.connect(self.shutdown)
        self.mainwindow.tabs.keypress.connect(self.keyparser.handle)
        self.keyparser.set_cmd_text.connect(
            self.mainwindow.status.cmd.on_set_cmd_text)
        self.mainwindow.tabs.set_cmd_text.connect(
            self.mainwindow.status.cmd.on_set_cmd_text)
        self.mainwindow.tabs.quit.connect(self.shutdown)
        self.mainwindow.status.cmd.got_cmd.connect(self.commandparser.run)
        self.mainwindow.status.cmd.got_search.connect(self.searchparser.search)
        self.mainwindow.status.cmd.got_search_rev.connect(
            self.searchparser.search_rev)
        self.mainwindow.status.cmd.returnPressed.connect(
            self.mainwindow.tabs.setFocus)
        self.commandparser.error.connect(self.mainwindow.status.disp_error)
        self.searchparser.do_search.connect(
            self.mainwindow.tabs.cur_search)
        self.keyparser.commandparser.error.connect(
            self.mainwindow.status.disp_error)
        self.keyparser.keystring_updated.connect(
            self.mainwindow.status.keystring.setText)

        self.mainwindow.show()
        self._python_hacks()
        timer = QTimer.singleShot(0, self._process_init_args)
        self.timers.append(timer)

    def _process_init_args(self):
        """Process initial positional args.

        URLs to open have no prefix, commands to execute begin with a colon.

        """
        # QNetworkAccessManager::createRequest will hang for over a second, so
        # we make sure the GUI is refreshed here, so the start seems faster.
        self.processEvents(QEventLoop.ExcludeUserInputEvents |
                           QEventLoop.ExcludeSocketNotifiers)
        opened_urls = False

        for e in self.args.command:
            if e.startswith(':'):
                logging.debug('Startup cmd {}'.format(e))
                self.commandparser.run(e.lstrip(':'))
            else:
                logging.debug('Startup url {}'.format(e))
                opened_urls = True
                self.mainwindow.tabs.tabopen(e)

        if not opened_urls:
            logging.debug('Opening startpage')
            # pylint: disable=maybe-no-member
            for url in config.config.get('general', 'startpage').split(','):
                self.mainwindow.tabs.tabopen(url)

    def _recover_pages(self):
        """Try to recover all open pages.

        Return a list of open pages, or an empty list.
        Called from _exception_hook, so as forgiving as possible.

        """
        pages = []
        if self.mainwindow is None:
            return pages
        if self.mainwindow.tabs is None:
            return pages
        for tabidx in range(self.mainwindow.tabs.count()):
            try:
                url = self.mainwindow.tabs.widget(tabidx).url().toString()
                if url:
                    pages.append(url)
            except Exception:  # pylint: disable=broad-except
                pass
        return pages

    def _exception_hook(self, exctype, excvalue, tb):
        """Handle uncaught python exceptions.

        It'll try very hard to write all open tabs to a file, and then exit
        gracefully.

        """
        # pylint: disable=broad-except

        exc = (exctype, excvalue, tb)
        sys.__excepthook__(*exc)

        if not (isinstance(exctype, Exception) or exctype is Exception):
            # probably a KeyboardInterrupt
            try:
                self.shutdown()
                return
            except Exception:
                self.quit()
        self._quit_status['crash'] = False
        self._quit_status['shutdown'] = False
        try:
            pages = self._recover_pages()
        except Exception:
            pages = []

        try:
            history = self.mainwindow.status.cmd.history[-5:]
        except Exception:
            history = []

        # Try to shutdown gracefully
        try:
            self.shutdown(do_quit=False)
        except Exception:
            pass
        try:
            self.lastWindowClosed.disconnect(self.shutdown)
        except TypeError:
            logging.exception("Preventing shutdown failed.")
        QApplication.closeAllWindows()
        dlg = CrashDialog(pages, history, exc)
        ret = dlg.exec_()
        if ret == QDialog.Accepted:  # restore
            os.environ['PYTHONPATH'] = os.pathsep.join(sys.path)
            # FIXME we might want to use argparse's features to not open pages
            # again if they were opened via cmdline
            argv = [sys.executable] + sys.argv + pages
            logging.debug('Running {} with args {}'.format(sys.executable,
                                                           argv))
            subprocess.Popen(argv)
        self._maybe_quit('crash')

    def _maybe_quit(self, sender):
        """Maybe quit qutebrowser.

        This only quits if both the CrashDialog was ready to quit AND the
        shutdown is complete.
        """
        self._quit_status[sender] = True
        logging.debug("maybe_quit called from {}, quit status {}".format(sender, self._quit_status))
        if all(self._quit_status.values()):
            self.quit()

    def _python_hacks(self):
        """Get around some PyQt-oddities by evil hacks.

        This sets up the uncaught exception hook, quits with an appropriate
        exit status, and handles Ctrl+C properly by passing control to the
        Python interpreter once all 500ms.

        """
        signal(SIGINT, lambda *args: self.exit(128 + SIGINT))
        timer = QTimer()
        timer.start(500)
        timer.timeout.connect(lambda: None)
        self.timers.append(timer)

    def _parseopts(self):
        """Parse command line options."""
        parser = ArgumentParser("usage: %(prog)s [options]")
        parser.add_argument('-l', '--log', dest='loglevel',
                            help='Set loglevel', default='info')
        parser.add_argument('-c', '--confdir', help='Set config directory '
                            '(empty for no config storage)')
        parser.add_argument('-d', '--debug', help='Turn on debugging options.',
                            action='store_true')
        parser.add_argument('command', nargs='*', help='Commands to execute '
                            'on startup.', metavar=':command')
        # URLs will actually be in command
        parser.add_argument('url', nargs='*', help='URLs to open on startup.')
        self.args = parser.parse_args()

    def _initlog(self):
        """Initialisation of the logging output."""
        loglevel = 'debug' if self.args.debug else self.args.loglevel
        numeric_level = getattr(logging, loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: {}'.format(loglevel))
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s [%(levelname)s] '
                   '[%(module)s:%(funcName)s:%(lineno)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')

    def _initmisc(self):
        """Initialize misc things."""
        if self.args.debug:
            os.environ['QT_FATAL_WARNINGS'] = '1'
        self.setApplicationName("qutebrowser")
        self.setApplicationVersion(qutebrowser.__version__)
        self.timers = []

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

    @pyqtSlot()
    def shutdown(self, do_quit=True):
        """Try to shutdown everything cleanly.

        For some reason lastWindowClosing sometimes seem to get emitted twice,
        so we make sure we only run once here.

        quit -- Whether to quit after shutting down.

        """
        if self.shutting_down:
            return
        self.shutting_down = True
        logging.debug("Shutting down... (do_quit={})".format(do_quit))
        if config.config is not None:
            config.config.save()
        try:
            if do_quit:
                self.mainwindow.tabs.shutdown_complete.connect(self.quit)
            else:
                self.mainwindow.tabs.shutdown_complete.connect(
                    functools.partial(self._maybe_quit, 'shutdown'))
            self.mainwindow.tabs.shutdown()
        except AttributeError:  # mainwindow or tabs could still be None
            logging.debug("No mainwindow/tabs to shut down.")
            if do_quit:
                self.quit()

    @pyqtSlot(tuple)
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
            'opencur':       self.mainwindow.tabs.opencur,
            'tabopen':       self.mainwindow.tabs.tabopen,
            'tabopencur':    self.mainwindow.tabs.tabopencur,
            'quit':          self.shutdown,
            'tabclose':      self.mainwindow.tabs.cur_close,
            'tabprev':       self.mainwindow.tabs.switch_prev,
            'tabnext':       self.mainwindow.tabs.switch_next,
            'reload':        self.mainwindow.tabs.cur_reload,
            'stop':          self.mainwindow.tabs.cur_stop,
            'back':          self.mainwindow.tabs.cur_back,
            'forward':       self.mainwindow.tabs.cur_forward,
            'print':         self.mainwindow.tabs.cur_print,
            'scroll':        self.mainwindow.tabs.cur_scroll,
            'scroll_page':   self.mainwindow.tabs.cur_scroll_page,
            'scroll_perc_x': self.mainwindow.tabs.cur_scroll_percent_x,
            'scroll_perc_y': self.mainwindow.tabs.cur_scroll_percent_y,
            'undo':          self.mainwindow.tabs.undo_close,
            'pyeval':        self.pyeval,
            'nextsearch':    self.searchparser.nextsearch,
            'yank':          self.mainwindow.tabs.cur_yank,
            'yanktitle':     self.mainwindow.tabs.cur_yank_title,
            'paste':         self.mainwindow.tabs.paste,
            'tabpaste':      self.mainwindow.tabs.tabpaste,
            'crash':         self.crash,
        }

        handler = handlers[cmd]

        if count is not None and self.sender().count:
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
        about.pyeval_output = out
        self.mainwindow.tabs.openurl('about:pyeval')

    def crash(self):
        """Crash for debugging purposes.

        :crash command handler.

        """
        raise Exception
