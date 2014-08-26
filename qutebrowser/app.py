# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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
import subprocess
import faulthandler
import configparser
import signal
import warnings
import bdb
import base64
import functools

from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt5.QtCore import (pyqtSlot, QTimer, QEventLoop, Qt, QStandardPaths,
                          qInstallMessageHandler, QObject, QUrl)

import qutebrowser
from qutebrowser.commands import userscripts, runners, cmdutils
from qutebrowser.config import (style, config, websettings, iniparsers,
                                lineparser, conftypes)
from qutebrowser.network import qutescheme, proxy
from qutebrowser.browser import quickmarks, cookies, downloads
from qutebrowser.widgets import mainwindow, console, crash
from qutebrowser.keyinput import modeparsers, keyparser, modeman
from qutebrowser.utils import (log, version, message, utilcmds, readline,
                               utils, qtutils, urlutils)
from qutebrowser.utils import usertypes as utypes


class Application(QApplication):

    """Main application instance.

    Attributes:
        mainwindow: The MainWindow QWidget.
        debugconsole: The ConsoleWidget for debugging.
        commandrunner: The main CommandRunner instance.
        searchrunner: The main SearchRunner instance.
        config: The main ConfigManager
        stateconfig: The "state" ReadWriteConfigParser instance.
        cmd_history: The "cmd_history" LineConfigParser instance.
        messagebridge: The global MessageBridge instance.
        modeman: The global ModeManager instance.
        cookiejar: The global CookieJar instance.
        rl_bridge: The ReadlineBridge being used.
        args: ArgumentParser instance.
        _keyparsers: A mapping from modes to keyparsers.
        _timers: List of used QTimers so they don't get GCed.
        _shutting_down: True if we're currently shutting down.
        _quit_status: The current quitting status.
        _crashdlg: The crash dialog currently open.
        _crashlogfile: A file handler to the fatal crash logfile.
    """

    def __init__(self, args):
        """Constructor.

        Args:
            Argument namespace from argparse.
        """
        # pylint: disable=too-many-statements
        if args.debug:
            # We don't enable this earlier because some imports trigger
            # warnings (which are not our fault).
            warnings.simplefilter('default')
        qt_args = qtutils.get_args(args)
        log.init.debug("Qt arguments: {}, based on {}".format(qt_args, args))
        super().__init__(qt_args)
        self._quit_status = {
            'crash': True,
            'tabs': False,
            'main': False,
        }
        self._timers = []
        self._shutting_down = False
        self._keyparsers = None
        self._crashdlg = None
        self._crashlogfile = None
        self.rl_bridge = None
        self.messagebridge = None
        self.stateconfig = None
        self.modeman = None
        self.cmd_history = None
        self.config = None

        sys.excepthook = self._exception_hook

        self.args = args
        log.init.debug("Starting init...")
        self._init_misc()
        utils.actute_warning()
        log.init.debug("Initializing config...")
        self._init_config()
        log.init.debug("Initializing crashlog...")
        self._handle_segfault()
        log.init.debug("Initializing modes...")
        self._init_modes()
        log.init.debug("Initializing websettings...")
        websettings.init()
        log.init.debug("Initializing quickmarks...")
        quickmarks.init()
        log.init.debug("Initializing proxy...")
        proxy.init()
        log.init.debug("Initializing userscripts...")
        userscripts.init()
        log.init.debug("Initializing utility commands...")
        utilcmds.init()
        log.init.debug("Initializing cookies...")
        self.cookiejar = cookies.CookieJar(self)
        log.init.debug("Initializing commands...")
        self.commandrunner = runners.CommandRunner()
        log.init.debug("Initializing search...")
        self.searchrunner = runners.SearchRunner(self)
        log.init.debug("Initializing downloads...")
        self.downloadmanager = downloads.DownloadManager(self)
        log.init.debug("Initializing main window...")
        self.mainwindow = mainwindow.MainWindow()
        self.modeman.mainwindow = self.mainwindow
        log.init.debug("Initializing debug console...")
        self.debugconsole = console.ConsoleWidget()
        log.init.debug("Initializing eventfilter...")
        self.installEventFilter(self.modeman)
        self.setQuitOnLastWindowClosed(False)

        log.init.debug("Connecting signals...")
        self._connect_signals()
        self.modeman.enter(utypes.KeyMode.normal, 'init')

        log.init.debug("Showing mainwindow...")
        if not args.nowindow:
            self.mainwindow.show()
        log.init.debug("Applying python hacks...")
        self._python_hacks()
        timer = QTimer.singleShot(0, self._process_init_args)
        self._timers.append(timer)

        log.init.debug("Init done!")

        if self._crashdlg is not None:
            self._crashdlg.raise_()

    def _init_config(self):
        """Inizialize and read the config."""
        if self.args.confdir is None:
            confdir = utils.get_standard_dir(QStandardPaths.ConfigLocation)
        elif self.args.confdir == '':
            confdir = None
        else:
            confdir = self.args.confdir
        try:
            self.config = config.ConfigManager(confdir, 'qutebrowser.conf',
                                               self)
        except (conftypes.ValidationError,
                config.NoOptionError,
                config.InterpolationSyntaxError,
                configparser.InterpolationError,
                configparser.DuplicateSectionError,
                configparser.DuplicateOptionError,
                configparser.ParsingError) as e:
            log.init.exception(e)
            errstr = "Error while reading config:"
            if hasattr(e, 'section') and hasattr(e, 'option'):
                errstr += "\n\n{} -> {}:".format(e.section, e.option)
            errstr += "\n{}".format(e)
            msgbox = QMessageBox(QMessageBox.Critical,
                                 "Error while reading config!", errstr)
            msgbox.exec_()
            # We didn't really initialize much so far, so we just quit hard.
            sys.exit(1)
        self.stateconfig = iniparsers.ReadWriteConfigParser(confdir, 'state')
        self.cmd_history = lineparser.LineConfigParser(
            confdir, 'cmd_history', ('completion', 'history-length'))

    def _init_modes(self):
        """Inizialize the mode manager and the keyparsers."""
        self._keyparsers = {
            utypes.KeyMode.normal:
                modeparsers.NormalKeyParser(self),
            utypes.KeyMode.hint:
                modeparsers.HintKeyParser(self),
            utypes.KeyMode.insert:
                keyparser.PassthroughKeyParser('keybind.insert', self),
            utypes.KeyMode.passthrough:
                keyparser.PassthroughKeyParser('keybind.passthrough', self),
            utypes.KeyMode.command:
                keyparser.PassthroughKeyParser('keybind.command', self),
            utypes.KeyMode.prompt:
                keyparser.PassthroughKeyParser('keybind.prompt', self,
                                               warn=False),
            utypes.KeyMode.yesno:
                modeparsers.PromptKeyParser(self),
        }
        self.modeman = modeman.ModeManager(self)
        self.modeman.register(utypes.KeyMode.normal,
                              self._keyparsers[utypes.KeyMode.normal].handle)
        self.modeman.register(utypes.KeyMode.hint,
                              self._keyparsers[utypes.KeyMode.hint].handle)
        self.modeman.register(utypes.KeyMode.insert,
                              self._keyparsers[utypes.KeyMode.insert].handle,
                              passthrough=True)
        self.modeman.register(
            utypes.KeyMode.passthrough,
            self._keyparsers[utypes.KeyMode.passthrough].handle,
            passthrough=True)
        self.modeman.register(utypes.KeyMode.command,
                              self._keyparsers[utypes.KeyMode.command].handle,
                              passthrough=True)
        self.modeman.register(utypes.KeyMode.prompt,
                              self._keyparsers[utypes.KeyMode.prompt].handle,
                              passthrough=True)
        self.modeman.register(utypes.KeyMode.yesno,
                              self._keyparsers[utypes.KeyMode.yesno].handle)

    def _init_misc(self):
        """Initialize misc things."""
        if self.args.version:
            print(version.version())
            print()
            print()
            print(qutebrowser.__copyright__)
            print()
            print(version.GPL_BOILERPLATE.strip())
            sys.exit(0)
        self.setOrganizationName("qutebrowser")
        self.setApplicationName("qutebrowser")
        self.setApplicationVersion(qutebrowser.__version__)
        self.messagebridge = message.MessageBridge(self)
        self.rl_bridge = readline.ReadlineBridge()

    def _handle_segfault(self):
        """Handle a segfault from a previous run."""
        # FIXME If an empty logfile exists, we log to stdout instead, which is
        # the only way to not break multiple instances.
        # However this also means if the logfile is there for some weird
        # reason, we'll *always* log to stderr, but that's still better than no
        # dialogs at all.
        path = utils.get_standard_dir(QStandardPaths.DataLocation)
        logname = os.path.join(path, 'crash.log')
        # First check if an old logfile exists.
        if os.path.exists(logname):
            with open(logname, 'r', encoding='ascii') as f:
                data = f.read()
            if data:
                # Crashlog exists and has data in it, so something crashed
                # previously.
                try:
                    os.remove(logname)
                except PermissionError:
                    log.init.warning("Could not remove crash log!")
                else:
                    self._init_crashlogfile()
                self._crashdlg = crash.FatalCrashDialog(data)
                self._crashdlg.show()
            else:
                # Crashlog exists but without data.
                # This means another instance is probably still running and
                # didn't remove the file. As we can't write to the same file,
                # we just leave faulthandler as it is and log to stderr.
                log.init.warning("Empty crash log detected. This means either "
                                 "another instance is running (then ignore "
                                 "this warning) or the file is lying here "
                                 "because of some earlier crash (then delete "
                                 "{}).".format(logname))
                self._crashlogfile = None
        else:
            # There's no log file, so we can use this to display crashes to the
            # user on the next start.
            self._init_crashlogfile()

    def _init_crashlogfile(self):
        """Start a new logfile and redirect faulthandler to it."""
        path = utils.get_standard_dir(QStandardPaths.DataLocation)
        logname = os.path.join(path, 'crash.log')
        self._crashlogfile = open(logname, 'w', encoding='ascii')
        faulthandler.enable(self._crashlogfile)
        if (hasattr(faulthandler, 'register') and
                hasattr(signal, 'SIGUSR1')):
            # If available, we also want a traceback on SIGUSR1.
            # pylint: disable=no-member
            faulthandler.register(signal.SIGUSR1)

    def _process_init_args(self):
        """Process initial positional args.

        URLs to open have no prefix, commands to execute begin with a colon.
        """
        # QNetworkAccessManager::createRequest will hang for over a second, so
        # we make sure the GUI is refreshed here, so the start seems faster.
        self.processEvents(QEventLoop.ExcludeUserInputEvents |
                           QEventLoop.ExcludeSocketNotifiers)

        for cmd in self.args.command:
            if cmd.startswith(':'):
                log.init.debug("Startup cmd {}".format(cmd))
                self.commandrunner.run_safely_init(cmd.lstrip(':'))
            else:
                log.init.debug("Startup URL {}".format(cmd))
                try:
                    url = urlutils.fuzzy_url(cmd)
                except urlutils.FuzzyUrlError as e:
                    message.error("Error in startup argument '{}': {}".format(
                        cmd, e))
                else:
                    self.mainwindow.tabs.tabopen(url)

        if self.mainwindow.tabs.count() == 0:
            log.init.debug("Opening startpage")
            for urlstr in self.config.get('general', 'startpage'):
                try:
                    url = urlutils.fuzzy_url(urlstr)
                except urlutils.FuzzyUrlError as e:
                    message.error("Error when opening startpage: {}".format(e))
                else:
                    self.mainwindow.tabs.tabopen(url)

    def _python_hacks(self):
        """Get around some PyQt-oddities by evil hacks.

        This sets up the uncaught exception hook, quits with an appropriate
        exit status, and handles Ctrl+C properly by passing control to the
        Python interpreter once all 500ms.
        """
        signal.signal(signal.SIGINT, self.interrupt)
        signal.signal(signal.SIGTERM, self.interrupt)
        timer = utypes.Timer(self, 'python_hacks')
        timer.start(500)
        timer.timeout.connect(lambda: None)
        self._timers.append(timer)

    def _connect_signals(self):
        """Connect all signals to their slots."""
        # pylint: disable=too-many-statements
        # syntactic sugar
        kp = self._keyparsers
        status = self.mainwindow.status
        completion = self.mainwindow.completion
        tabs = self.mainwindow.tabs
        cmd = self.mainwindow.status.cmd
        completer = self.mainwindow.completion.completer

        # misc
        self.lastWindowClosed.connect(self.shutdown)
        tabs.quit.connect(self.shutdown)

        # status bar
        self.modeman.entered.connect(status.on_mode_entered)
        self.modeman.left.connect(status.on_mode_left)
        self.modeman.left.connect(status.cmd.on_mode_left)
        self.modeman.left.connect(status.prompt.prompter.on_mode_left)

        # commands
        cmd.got_cmd.connect(self.commandrunner.run_safely)
        cmd.got_search.connect(self.searchrunner.search)
        cmd.got_search_rev.connect(self.searchrunner.search_rev)
        cmd.returnPressed.connect(tabs.setFocus)
        self.searchrunner.do_search.connect(tabs.search)
        kp[utypes.KeyMode.normal].keystring_updated.connect(
            status.keystring.setText)
        tabs.got_cmd.connect(self.commandrunner.run_safely)

        # hints
        kp[utypes.KeyMode.hint].fire_hint.connect(tabs.fire_hint)
        kp[utypes.KeyMode.hint].filter_hints.connect(tabs.filter_hints)
        kp[utypes.KeyMode.hint].keystring_updated.connect(tabs.handle_hint_key)
        tabs.hint_strings_updated.connect(
            kp[utypes.KeyMode.hint].on_hint_strings_updated)

        # messages
        self.messagebridge.s_error.connect(status.disp_error)
        self.messagebridge.s_info.connect(status.disp_temp_text)
        self.messagebridge.s_set_text.connect(status.set_text)
        self.messagebridge.s_set_cmd_text.connect(cmd.set_cmd_text)
        self.messagebridge.s_question.connect(
            status.prompt.prompter.ask_question, Qt.DirectConnection)

        # config
        self.config.style_changed.connect(style.invalidate_caches)
        for obj in (tabs, completion, self.mainwindow, self.cmd_history,
                    websettings, kp[utypes.KeyMode.normal], self.modeman,
                    status, status.txt):
            self.config.changed.connect(obj.on_config_changed)

        # statusbar
        # FIXME some of these probably only should be triggered on mainframe
        # loadStarted.
        tabs.current_tab_changed.connect(status.prog.on_tab_changed)
        tabs.cur_progress.connect(status.prog.setValue)
        tabs.cur_load_finished.connect(status.prog.hide)
        tabs.cur_load_started.connect(status.prog.on_load_started)

        tabs.current_tab_changed.connect(status.percentage.on_tab_changed)
        tabs.cur_scroll_perc_changed.connect(status.percentage.set_perc)

        tabs.current_tab_changed.connect(status.txt.on_tab_changed)
        tabs.cur_statusbar_message.connect(status.txt.on_statusbar_message)
        tabs.cur_load_started.connect(status.txt.on_load_started)

        tabs.current_tab_changed.connect(status.url.on_tab_changed)
        tabs.cur_url_text_changed.connect(status.url.set_url)
        tabs.cur_link_hovered.connect(status.url.set_hover_url)
        tabs.cur_load_status_changed.connect(status.url.on_load_status_changed)

        # command input / completion
        self.modeman.left.connect(tabs.on_mode_left)
        cmd.clear_completion_selection.connect(
            completion.on_clear_completion_selection)
        cmd.hide_completion.connect(completion.hide)
        cmd.update_completion.connect(completer.on_update_completion)
        completer.change_completed_part.connect(cmd.on_change_completed_part)

        # downloads
        tabs.start_download.connect(self.downloadmanager.fetch)
        tabs.download_get.connect(self.downloadmanager.get)

    def get_all_widgets(self):
        """Get a string list of all widgets."""
        lines = []
        widgets = self.allWidgets()
        widgets.sort(key=lambda e: repr(e))
        lines.append("{} widgets".format(len(widgets)))
        for w in widgets:
            lines.append(repr(w))
        return '\n'.join(lines)

    def get_all_objects(self, obj=None, depth=0, lines=None):
        """Get all children of an object recursively as a string."""
        if lines is None:
            lines = []
        if obj is None:
            obj = self
        for kid in obj.findChildren(QObject):
            lines.append('    ' * depth + repr(kid))
            self.get_all_objects(kid, depth + 1, lines)
        if depth == 0:
            lines.insert(0, '{} objects:'.format(len(lines)))
        return '\n'.join(lines)

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
        for tab in self.mainwindow.tabs.widgets:
            try:
                url = tab.cur_url.toString(
                    QUrl.RemovePassword | QUrl.FullyEncoded)
                if url:
                    pages.append(url)
            except Exception as e:  # pylint: disable=broad-except
                log.destroy.debug("Error while recovering tab: {}: {}".format(
                    e.__class__.__name__, e))
        return pages

    def _save_geometry(self):
        """Save the window geometry to the state config."""
        data = bytes(self.mainwindow.saveGeometry())
        geom = base64.b64encode(data).decode('ASCII')
        try:
            self.stateconfig.add_section('geometry')
        except configparser.DuplicateSectionError:
            pass
        self.stateconfig['geometry']['mainwindow'] = geom

    def _destroy_crashlogfile(self):
        """Clean up the crash log file and delete it."""
        if self._crashlogfile is None:
            return
        # We use sys.__stderr__ instead of sys.stderr here so this will still
        # work when sys.stderr got replaced, e.g. by "Python Tools for Visual
        # Studio".
        if sys.__stderr__ is not None:
            faulthandler.enable(sys.__stderr__)
        else:
            faulthandler.disable()
        self._crashlogfile.close()
        try:
            os.remove(self._crashlogfile.name)
        except (PermissionError, FileNotFoundError) as e:
            log.destroy.warning("Could not remove crash log ({})!".format(e))

    def _exception_hook(self, exctype, excvalue, tb):
        """Handle uncaught python exceptions.

        It'll try very hard to write all open tabs to a file, and then exit
        gracefully.
        """
        # pylint: disable=broad-except

        if exctype is bdb.BdbQuit or not issubclass(exctype, Exception):
            # pdb exit, KeyboardInterrupt, ...
            try:
                self.shutdown()
                return
            except Exception as e:
                log.init.debug("Error while shutting down: {}: {}".format(
                    e.__class__.__name__, e))
                self.quit()
                return

        exc = (exctype, excvalue, tb)
        sys.__excepthook__(*exc)

        self._quit_status['crash'] = False

        try:
            pages = self._recover_pages()
        except Exception as e:
            log.destroy.debug("Error while recovering pages: {}: {}".format(
                e.__class__.__name__, e))
            pages = []

        try:
            history = self.mainwindow.status.cmd.history[-5:]
        except Exception as e:
            log.destroy.debug("Error while getting history: {}: {}".format(
                e.__class__.__name__, e))
            history = []

        try:
            widgets = self.get_all_widgets()
        except Exception as e:
            log.destroy.debug("Error while getting widgets: {}: {}".format(
                e.__class__.__name__, e))
            widgets = ""

        try:
            objects = self.get_all_objects()
        except Exception as e:
            log.destroy.debug("Error while getting objects: {}: {}".format(
                e.__class__.__name__, e))
            objects = ""

        try:
            self.lastWindowClosed.disconnect(self.shutdown)
        except TypeError as e:
            log.destroy.debug("Error while preventing shutdown: {}: {}".format(
                e.__class__.__name__, e))
        QApplication.closeAllWindows()
        self._crashdlg = crash.ExceptionCrashDialog(pages, history, exc,
                                                    widgets, objects)
        ret = self._crashdlg.exec_()
        if ret == QDialog.Accepted:  # restore
            self.restart(shutdown=False, pages=pages)
        # We might risk a segfault here, but that's better than continuing to
        # run in some undefined state, so we only do the most needed shutdown
        # here.
        qInstallMessageHandler(None)
        self._destroy_crashlogfile()
        sys.exit(1)

    @cmdutils.register(instance='', nargs=0)
    def restart(self, shutdown=True, pages=None):
        """Restart qutebrowser while keeping existing tabs open."""
        # We don't use _recover_pages here as it's too forgiving when
        # exceptions occur.
        if pages is None:
            pages = []
            for tab in self.mainwindow.tabs.widgets:
                urlstr = tab.cur_url.toString(
                    QUrl.RemovePassword | QUrl.FullyEncoded)
                if urlstr:
                    pages.append(urlstr)
        log.destroy.debug("sys.executable: {}".format(sys.executable))
        log.destroy.debug("sys.path: {}".format(sys.path))
        log.destroy.debug("sys.argv: {}".format(sys.argv))
        log.destroy.debug("frozen: {}".format(hasattr(sys, 'frozen')))
        if hasattr(sys, 'frozen'):
            args = [sys.executable]
            cwd = os.path.abspath(os.path.dirname(sys.executable))
        else:
            args = [sys.executable, '-m', 'qutebrowser']
            cwd = os.path.join(os.path.abspath(os.path.dirname(
                               qutebrowser.__file__)), '..')
        for arg in sys.argv[1:]:
            if arg.startswith('-'):
                # We only want to preserve options on a restart.
                args.append(arg)
        # Add all open pages so they get reopened.
        args += pages
        log.destroy.debug("args: {}".format(args))
        log.destroy.debug("cwd: {}".format(cwd))
        # Open a new process and immediately shutdown the existing one
        subprocess.Popen(args, cwd=cwd)
        if shutdown:
            self.shutdown()

    @cmdutils.register(instance='', split=False, debug=True)
    def debug_pyeval(self, s):
        """Evaluate a python string and display the results as a webpage.

        //

        We have this here rather in utils.debug so the context of eval makes
        more sense and because we don't want to import much stuff in the utils.

        Args:
            s: The string to evaluate.
        """
        try:
            r = eval(s)  # pylint: disable=eval-used
            out = repr(r)
        except Exception as e:  # pylint: disable=broad-except
            out = ': '.join([e.__class__.__name__, str(e)])
        qutescheme.pyeval_output = out
        self.mainwindow.tabs.openurl(QUrl('qute:pyeval'), newtab=True)

    @cmdutils.register(instance='')
    def report(self):
        """Report a bug in qutebrowser."""
        pages = self._recover_pages()
        history = self.mainwindow.status.cmd.history[-5:]
        widgets = self.get_all_widgets()
        objects = self.get_all_objects()
        self._crashdlg = crash.ReportDialog(pages, history, widgets, objects)
        self._crashdlg.show()

    @cmdutils.register(instance='', debug=True, name='debug-console')
    def show_debugconsole(self):
        """Show the debugging console."""
        self.debugconsole.show()

    def interrupt(self, signum, _frame):
        """Handler for signals to gracefully shutdown (SIGINT/SIGTERM).

        This calls self.shutdown and remaps the signal to call
        self.interrupt_forcefully the next time.
        """
        log.destroy.info("SIGINT/SIGTERM received, shutting down!")
        log.destroy.info("Do the same again to forcefully quit.")
        signal.signal(signal.SIGINT, self.interrupt_forcefully)
        signal.signal(signal.SIGTERM, self.interrupt_forcefully)
        # If we call shutdown directly here, we get a segfault.
        QTimer.singleShot(0, functools.partial(self.shutdown, 128 + signum))

    def interrupt_forcefully(self, signum, _frame):
        """Interrupt forcefully on the second SIGINT/SIGTERM request.

        This skips our shutdown routine and calls QApplication:exit instead.
        It then remaps the signals to call self.interrupt_really_forcefully the
        next time.
        """
        log.destroy.info("Forceful quit requested, goodbye cruel world!")
        log.destroy.info("Do the same again to quit with even more force.")
        signal.signal(signal.SIGINT, self.interrupt_really_forcefully)
        signal.signal(signal.SIGTERM, self.interrupt_really_forcefully)
        # This *should* work without a QTimer, but because of the trouble in
        # self.interrupt we're better safe than sorry.
        QTimer.singleShot(0, functools.partial(self.exit, 128 + signum))

    def interrupt_really_forcefully(self, signum, _frame):
        """Interrupt with even more force on the third SIGINT/SIGTERM request.

        This doesn't run *any* Qt cleanup and simply exits via Python.
        It will most likely lead to a segfault.
        """
        log.destroy.info("WHY ARE YOU DOING THIS TO ME? :(")
        sys.exit(128 + signum)

    @pyqtSlot()
    def shutdown(self, status=0):
        """Try to shutdown everything cleanly.

        For some reason lastWindowClosing sometimes seem to get emitted twice,
        so we make sure we only run once here.

        Args:
            status: The status code to exit with.
        """
        if self._shutting_down:
            return
        self._shutting_down = True
        log.destroy.debug("Shutting down with status {}...".format(status))
        if self.mainwindow.status.prompt.prompter.shutdown():
            # If shutdown was called while we were asking a question, we're in
            # a still sub-eventloop (which gets quitted now) and not in the
            # main one.
            # This means we need to defer the real shutdown to when we're back
            # in the real main event loop, or we'll get a segfault.
            log.destroy.debug("Deferring real shutdown because question was "
                              "active.")
            QTimer.singleShot(0, functools.partial(self._shutdown, status))
        else:
            # If we have no questions to shut down, we are already in the real
            # event loop, so we can shut down immediately.
            self._shutdown(status)

    def _shutdown(self, status):
        """Second stage of shutdown."""
        log.destroy.debug("Stage 2 of shutting down...")
        # Remove eventfilter
        if self.modeman is not None:
            log.destroy.debug("Removing eventfilter...")
            self.removeEventFilter(self.modeman)
        # Close all tabs
        if self.mainwindow is not None:
            log.destroy.debug("Closing tabs...")
            self.mainwindow.tabs.shutdown()
        # Save everything
        if hasattr(self, 'config') and self.config is not None:
            to_save = []
            if self.config.get('general', 'auto-save-config'):
                to_save.append(("config", self.config.save))
            to_save += [("window geometry", self._save_geometry),
                        ("quickmarks", quickmarks.save)]
            if hasattr(self, 'cmd_history'):
                to_save.append(("command history", self.cmd_history.save))
            if hasattr(self, 'stateconfig'):
                to_save.append(("window geometry", self.stateconfig.save))
            if hasattr(self, 'cookiejar'):
                to_save.append(("cookies", self.cookiejar.save))
            for what, handler in to_save:
                log.destroy.debug("Saving {} (handler: {})".format(
                    what, handler.__qualname__))
                try:
                    handler()
                except AttributeError as e:
                    log.destroy.warning("Could not save {}.".format(what))
                    log.destroy.debug(e)
        else:
            log.destroy.debug("Config not initialized yet, so not saving "
                              "anything.")
        # Re-enable faulthandler to stdout, then remove crash log
        log.destroy.debug("Deactiving crash log...")
        self._destroy_crashlogfile()
        # If we don't kill our custom handler here we might get segfaults
        log.destroy.debug("Deactiving message handler...")
        qInstallMessageHandler(None)
        # Now we can hopefully quit without segfaults
        log.destroy.debug("Deferring QApplication::exit...")
        # We use a singleshot timer to exit here to minimize the likelyhood of
        # segfaults.
        QTimer.singleShot(0, functools.partial(self.exit, status))

    def exit(self, status):
        """Extend QApplication::exit to log the event."""
        log.destroy.debug("Now calling QApplication::exit.")
        super().exit(status)
