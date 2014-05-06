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
import subprocess
import configparser
from bdb import BdbQuit
from functools import partial
from signal import signal, SIGINT
from argparse import ArgumentParser
from base64 import b64encode
# Print a nice traceback on segfault -- only available on Python 3.3+, but if
# it's unavailable, it doesn't matter much.
try:
    import faulthandler  # pylint: disable=import-error
except ImportError:
    pass
else:
    faulthandler.enable()

# This is a really odd place to do this, but we have to do this before
# importing PyQt or it won't work.
# See https://bugreports.qt-project.org/browse/QTBUG-36099
import qutebrowser.utils.harfbuzz as harfbuzz
harfbuzz.fix()

from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt5.QtCore import pyqtSlot, QTimer, QEventLoop
from appdirs import AppDirs

import qutebrowser
import qutebrowser.commands.utils as cmdutils
import qutebrowser.config.style as style
import qutebrowser.config.config as config
import qutebrowser.network.qutescheme as qutescheme
import qutebrowser.config.websettings as websettings
import qutebrowser.network.proxy as proxy
from qutebrowser.network.networkmanager import NetworkManager
from qutebrowser.config.config import ConfigManager
from qutebrowser.keyinput.modeman import ModeManager
from qutebrowser.widgets.mainwindow import MainWindow
from qutebrowser.widgets.crash import CrashDialog
from qutebrowser.keyinput.modeparsers import NormalKeyParser, HintKeyParser
from qutebrowser.keyinput.keyparser import PassthroughKeyParser
from qutebrowser.commands.managers import CommandManager, SearchManager
from qutebrowser.config.iniparsers import ReadWriteConfigParser
from qutebrowser.config.lineparser import LineConfigParser
from qutebrowser.browser.cookies import CookieJar
from qutebrowser.utils.message import MessageBridge
from qutebrowser.utils.misc import dotted_getattr
from qutebrowser.utils.debug import set_trace  # pylint: disable=unused-import


class QuteBrowser(QApplication):

    """Main object for qutebrowser.

    Can be used like this:

    >>> app = QuteBrowser()
    >>> sys.exit(app.exec_())

    Attributes:
        mainwindow: The MainWindow QWidget.
        commandmanager: The main CommandManager instance.
        searchmanager: The main SearchManager instance.
        config: The main ConfigManager
        stateconfig: The "state" ReadWriteConfigParser instance.
        cmd_history: The "cmd_history" LineConfigParser instance.
        messagebridge: The global MessageBridge instance.
        modeman: The global ModeManager instance.
        networkmanager: The global NetworkManager instance.
        cookiejar: The global CookieJar instance.
        _keyparsers: A mapping from modes to keyparsers.
        _dirs: AppDirs instance for config/cache directories.
        _args: ArgumentParser instance.
        _timers: List of used QTimers so they don't get GCed.
        _shutting_down: True if we're currently shutting down.
        _quit_status: The current quitting status.
        _opened_urls: List of opened URLs.
    """

    # This also holds all our globals, so we're a bit over the top here.
    # pylint: disable=too-many-instance-attributes

    def __init__(self):
        super().__init__(sys.argv)
        self._quit_status = {
            'crash': True,
            'tabs': False,
            'networkmanager': False
        }
        self._timers = []
        self._opened_urls = []
        self._shutting_down = False
        self._keyparsers = None
        self._dirs = None
        self.messagebridge = None
        self.stateconfig = None
        self.modeman = None
        self.cmd_history = None
        self.config = None

        sys.excepthook = self._exception_hook

        self._args = self._parse_args()
        self._init_log()
        self._init_misc()
        self._init_config()
        self._init_modes()
        websettings.init(self._dirs.user_cache_dir)
        proxy.init()
        self.cookiejar = CookieJar(self._dirs.user_data_dir)
        self.networkmanager = NetworkManager(self.cookiejar)
        self.commandmanager = CommandManager()
        self.searchmanager = SearchManager()
        self._init_cmds()
        self.mainwindow = MainWindow()

        self.installEventFilter(self.modeman)
        self.setQuitOnLastWindowClosed(False)

        self._connect_signals()
        self.modeman.enter('normal')

        self.mainwindow.show()
        self._python_hacks()
        timer = QTimer.singleShot(0, self._process_init_args)
        self._timers.append(timer)

    def _parse_args(self):
        """Parse command line options.

        Return:
            Argument namespace from argparse.
        """
        parser = ArgumentParser("usage: %(prog)s [options]")
        parser.add_argument('-l', '--log', dest='loglevel',
                            help="Set loglevel", default='info')
        parser.add_argument('-c', '--confdir', help="Set config directory "
                            "(empty for no config storage)")
        parser.add_argument('-d', '--debug', help="Turn on debugging options.",
                            action='store_true')
        parser.add_argument('command', nargs='*', help="Commands to execute "
                            "on startup.", metavar=':command')
        # URLs will actually be in command
        parser.add_argument('url', nargs='*', help="URLs to open on startup.")
        return parser.parse_args()

    def _init_config(self):
        """Inizialize and read the config."""
        self._dirs = AppDirs('qutebrowser')
        if self._args.confdir is None:
            confdir = self._dirs.user_config_dir
        elif self._args.confdir == '':
            confdir = None
        else:
            confdir = self._args.confdir
        try:
            self.config = ConfigManager(confdir, 'qutebrowser.conf')
        except (config.ValidationError,
                config.NoOptionError,
                configparser.InterpolationError,
                configparser.DuplicateSectionError,
                configparser.DuplicateOptionError,
                configparser.ParsingError,
                ValueError) as e:
            errstr = "Error while reading config:"
            if hasattr(e, 'section') and hasattr(e, 'option'):
                errstr += "\n\n{} -> {}:".format(e.section, e.option)
            errstr += "\n{}".format(e)
            msgbox = QMessageBox(QMessageBox.Critical,
                                 "Error while reading config!", errstr)
            msgbox.exec_()
            # We didn't really initialize much so far, so we just quit hard.
            sys.exit(1)
        self.stateconfig = ReadWriteConfigParser(confdir, 'state')
        self.cmd_history = LineConfigParser(confdir, 'cmd_history',
                                            ('completion', 'history-length'))

    def _init_modes(self):
        """Inizialize the mode manager and the keyparsers."""
        self._keyparsers = {
            'normal': NormalKeyParser(self),
            'hint': HintKeyParser(self),
            'insert': PassthroughKeyParser('keybind.insert', self),
            'passthrough': PassthroughKeyParser('keybind.passthrough', self),
            'command': PassthroughKeyParser('keybind.command', self),
        }
        self.modeman = ModeManager()
        self.modeman.register('normal', self._keyparsers['normal'].handle)
        self.modeman.register('hint', self._keyparsers['hint'].handle)
        self.modeman.register('insert', self._keyparsers['insert'].handle,
                              passthrough=True)
        self.modeman.register('passthrough',
                              self._keyparsers['passthrough'].handle,
                              passthrough=True)
        self.modeman.register('command', self._keyparsers['command'].handle,
                              passthrough=True)

    def _init_log(self):
        """Initialisation of the logging output.

        Raise:
            ValueError if there was an invalid loglevel.
        """
        loglevel = 'debug' if self._args.debug else self._args.loglevel
        numeric_level = getattr(logging, loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError("Invalid log level: {}".format(loglevel))
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s [%(levelname)s] '
                   '[%(module)s:%(funcName)s:%(lineno)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')

    def _init_misc(self):
        """Initialize misc things."""
        if self._args.debug:
            os.environ['QT_FATAL_WARNINGS'] = '1'
        self.setApplicationName("qutebrowser")
        self.setApplicationVersion(qutebrowser.__version__)
        self.messagebridge = MessageBridge()

    def _init_cmds(self):
        """Initialisation of the qutebrowser commands.

        Registers all commands and connects their signals.
        """
        for key, cmd in sorted(cmdutils.cmd_dict.items()):
            cmd.signal.connect(self.command_handler)
            if cmd.instance is not None:
                func = '.'.join([cmd.instance if cmd.instance else 'app',
                                 cmd.handler.__name__])
            else:
                func = cmd.handler.__name__
            logging.debug("Registered command: {} -> {}".format(key, func))

    def _process_init_args(self):
        """Process initial positional args.

        URLs to open have no prefix, commands to execute begin with a colon.
        """
        # QNetworkAccessManager::createRequest will hang for over a second, so
        # we make sure the GUI is refreshed here, so the start seems faster.
        self.processEvents(QEventLoop.ExcludeUserInputEvents |
                           QEventLoop.ExcludeSocketNotifiers)

        for e in self._args.command:
            if e.startswith(':'):
                logging.debug("Startup cmd {}".format(e))
                self.commandmanager.run_safely(e.lstrip(':'))
            else:
                logging.debug("Startup url {}".format(e))
                self._opened_urls.append(e)
                self.mainwindow.tabs.tabopen(e)

        if self.mainwindow.tabs.count() == 0:
            logging.debug("Opening startpage")
            for url in self.config.get('general', 'startpage'):
                self.mainwindow.tabs.tabopen(url)

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
        self._timers.append(timer)

    def _connect_signals(self):
        """Connect all signals to their slots."""
        # syntactic sugar
        kp = self._keyparsers
        status = self.mainwindow.status
        completion = self.mainwindow.completion
        tabs = self.mainwindow.tabs
        cmd = self.mainwindow.status.cmd

        # misc
        self.lastWindowClosed.connect(self.shutdown)
        tabs.quit.connect(self.shutdown)
        tabs.currentChanged.connect(self.mainwindow.update_inspector)

        # status bar
        self.modeman.entered.connect(status.on_mode_entered)
        self.modeman.left.connect(status.on_mode_left)
        self.modeman.left.connect(status.cmd.on_mode_left)
        self.modeman.key_pressed.connect(status.on_key_pressed)

        # commands
        cmd.got_cmd.connect(self.commandmanager.run_safely)
        cmd.got_search.connect(self.searchmanager.search)
        cmd.got_search_rev.connect(self.searchmanager.search_rev)
        cmd.returnPressed.connect(tabs.setFocus)
        self.searchmanager.do_search.connect(tabs.cur.search)
        kp['normal'].keystring_updated.connect(status.keystring.setText)

        # hints
        kp['hint'].fire_hint.connect(tabs.cur.fire_hint)
        kp['hint'].filter_hints.connect(tabs.cur.filter_hints)
        kp['hint'].keystring_updated.connect(tabs.cur.handle_hint_key)
        tabs.hint_strings_updated.connect(kp['hint'].on_hint_strings_updated)

        # messages
        self.messagebridge.error.connect(status.disp_error)
        self.messagebridge.info.connect(status.txt.set_temptext)
        self.messagebridge.text.connect(status.txt.set_normaltext)
        self.messagebridge.set_cmd_text.connect(cmd.set_cmd_text)

        # config
        self.config.style_changed.connect(style.invalidate_caches)
        for obj in [tabs, completion, self.mainwindow, self.cmd_history,
                    websettings, kp['normal'], self.modeman]:
            self.config.changed.connect(obj.on_config_changed)

        # statusbar
        tabs.cur_progress.connect(status.prog.setValue)
        tabs.cur_load_finished.connect(status.prog.hide)
        tabs.cur_load_finished.connect(status.url.on_loading_finished)
        tabs.cur_load_started.connect(status.prog.on_load_started)
        tabs.cur_scroll_perc_changed.connect(status.percentage.set_perc)
        tabs.cur_statusbar_message.connect(status.txt.on_statusbar_message)
        tabs.cur_url_changed.connect(status.url.set_url)
        tabs.cur_link_hovered.connect(status.url.set_hover_url)

        # command input / completion
        self.modeman.left.connect(tabs.on_mode_left)
        cmd.clear_completion_selection.connect(
            completion.on_clear_completion_selection)
        cmd.hide_completion.connect(completion.hide)
        cmd.textEdited.connect(completion.on_cmd_text_changed)
        completion.change_completed_part.connect(cmd.on_change_completed_part)

    def _recover_pages(self):
        """Try to recover all open pages.

        Called from _exception_hook, so as forgiving as possible.

        Return:
            A list of open pages, or an empty list.
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

    def _save_geometry(self):
        """Save the window geometry to the state config."""
        geom = b64encode(bytes(self.mainwindow.saveGeometry())).decode('ASCII')
        try:
            self.stateconfig.add_section('geometry')
        except configparser.DuplicateSectionError:
            pass
        self.stateconfig['geometry']['mainwindow'] = geom

    def _exception_hook(self, exctype, excvalue, tb):
        """Handle uncaught python exceptions.

        It'll try very hard to write all open tabs to a file, and then exit
        gracefully.
        """
        # pylint: disable=broad-except

        exc = (exctype, excvalue, tb)
        sys.__excepthook__(*exc)

        self._quit_status['crash'] = False

        # Give key input back for crash dialog
        try:
            self.removeEventFilter(self.modeman)
        except AttributeError:
            # self.modeman could be None
            pass

        if exctype is BdbQuit or not issubclass(exctype, Exception):
            # pdb exit, KeyboardInterrupt, ...
            try:
                self.shutdown()
                return
            except Exception:
                self.quit()
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
            argv = sys.argv[:]
            for page in self._opened_urls:
                try:
                    argv.remove(page)
                except ValueError:
                    pass
            argv = [sys.executable] + argv + pages
            logging.debug("Running {} with args {}".format(sys.executable,
                                                           argv))
            subprocess.Popen(argv)
        self._maybe_quit('crash')

    def _maybe_quit(self, sender):
        """Maybe quit qutebrowser.

        This only quits if both the CrashDialog was ready to quit AND the
        shutdown is complete.

        Args:
            The sender of the quit signal (string)
        """
        self._quit_status[sender] = True
        logging.debug("maybe_quit called from {}, quit status {}".format(
            sender, self._quit_status))
        if all(self._quit_status.values()):
            logging.debug("maybe_quit quitting.")
            self.quit()

    @cmdutils.register(instance='', split=False)
    def pyeval(self, s):
        """Evaluate a python string and display the results as a webpage.

        :pyeval command handler.

        Args:
            s: The string to evaluate.
        """
        try:
            r = eval(s)  # pylint: disable=eval-used
            out = repr(r)
        except Exception as e:  # pylint: disable=broad-except
            out = ': '.join([e.__class__.__name__, str(e)])
        qutescheme.pyeval_output = out
        self.mainwindow.tabs.cur.openurl('qute:pyeval')

    @cmdutils.register(instance='', hide=True)
    def crash(self):
        """Crash for debugging purposes.

        :crash command handler.

        Raises:
            Always raises Exception.
        """
        raise Exception("Forced crash")

    @pyqtSlot()
    @cmdutils.register(instance='', name=['quit', 'q'], nargs=0)
    def shutdown(self):
        """Try to shutdown everything cleanly.

        For some reason lastWindowClosing sometimes seem to get emitted twice,
        so we make sure we only run once here.
        """
        if self._shutting_down:
            return
        self._shutting_down = True
        logging.debug("Shutting down...")
        # Save config
        if self.config.get('general', 'auto-save-config'):
            try:
                self.config.save()
            except AttributeError:
                logging.exception("Could not save config.")
        # Save command history
        try:
            self.cmd_history.save()
        except AttributeError:
            logging.exception("Could not save command history.")
        # Save window state
        try:
            self._save_geometry()
            self.stateconfig.save()
        except AttributeError:
            logging.exception("Could not save window geometry.")
        # Save cookies
        try:
            self.cookiejar.save()
        except AttributeError:
            logging.exception("Could not save cookies.")
        # Shut down tabs
        try:
            self.mainwindow.tabs.shutdown_complete.connect(partial(
                self._maybe_quit, 'tabs'))
            self.mainwindow.tabs.shutdown()
        except AttributeError:  # mainwindow or tabs could still be None
            logging.exception("No mainwindow/tabs to shut down.")
            self._maybe_quit('tabs')
        # Shut down networkmanager
        try:
            self.networkmanager.abort_requests()
            self.networkmanager.destroyed.connect(partial(
                self._maybe_quit, 'networkmanager'))
            self.networkmanager.deleteLater()
        except AttributeError:
            logging.exception("No networkmanager to shut down.")
            self._maybe_quit('networkmanager')

    @pyqtSlot()
    def on_tab_shutdown_complete(self):
        """Quit application after a shutdown.

        Gets called when all tabs finished shutting down after shutdown().
        """
        logging.debug("Shutdown complete, quitting.")
        self.quit()

    @pyqtSlot(tuple)
    def command_handler(self, tpl):
        """Handle commands which need an instance..

        Args:
            tpl: An (instance, func, count, args) tuple.
                instance: How to get the current instance of the target object
                          from app.py, as a dotted string, e.g.
                          'mainwindow.tabs.cur'.
                func:     The function name to be called (as string).
                count:    The count given to the command, or None.
                args:     A list of arguments given to the command.
        """
        (instance, func, count, args) = tpl
        if instance == '':
            obj = self
        else:
            obj = dotted_getattr(self, instance)
        handler = getattr(obj, func)
        if count is not None:
            handler(*args, count=count)
        else:
            handler(*args)
