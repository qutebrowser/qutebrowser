# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import configparser
import signal
import warnings
import bdb
import base64
import functools
import traceback
import faulthandler

from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt5.QtGui import QDesktopServices, QPixmap, QIcon
from PyQt5.QtCore import (pyqtSlot, qInstallMessageHandler, QTimer, QUrl,
                          QStandardPaths, QObject, Qt)

import qutebrowser
import qutebrowser.resources  # pylint: disable=unused-import
from qutebrowser.commands import cmdutils, runners
from qutebrowser.config import style, config, websettings
from qutebrowser.browser import quickmarks, cookies, cache, adblock
from qutebrowser.browser.network import qutescheme, proxy
from qutebrowser.mainwindow import mainwindow
from qutebrowser.misc import crashdialog, readline, ipc, earlyinit
from qutebrowser.misc import utilcmds  # pylint: disable=unused-import
from qutebrowser.keyinput import modeman
from qutebrowser.utils import (log, version, message, utils, qtutils, urlutils,
                               debug, objreg, usertypes, standarddir)
# We import utilcmds to run the cmdutils.register decorators.


class Application(QApplication):

    """Main application instance.

    Attributes:
        _args: ArgumentParser instance.
        _shutting_down: True if we're currently shutting down.
        _quit_status: The current quitting status.
        _crashdlg: The crash dialog currently open.
        _crashlogfile: A file handler to the fatal crash logfile.
        _event_filter: The EventFilter for the application.
        geometry: The geometry of the last closed main window.
    """

    def __init__(self, args):
        """Constructor.

        Args:
            Argument namespace from argparse.
        """
        # pylint: disable=too-many-statements
        self._quit_status = {
            'crash': True,
            'tabs': False,
            'main': False,
        }
        self.geometry = None
        self._shutting_down = False
        self._crashdlg = None
        self._crashlogfile = None

        if args.debug:
            # We don't enable this earlier because some imports trigger
            # warnings (which are not our fault).
            warnings.simplefilter('default')

        qt_args = qtutils.get_args(args)
        log.init.debug("Qt arguments: {}, based on {}".format(qt_args, args))
        super().__init__(qt_args)
        sys.excepthook = self._exception_hook

        self._args = args
        objreg.register('args', args)

        objreg.register('app', self)

        if self._args.version:
            print(version.version())
            print()
            print()
            print(qutebrowser.__copyright__)
            print()
            print(version.GPL_BOILERPLATE.strip())
            sys.exit(0)

        try:
            sent = ipc.send_to_running_instance(self._args.command)
            if sent:
                sys.exit(0)
            log.init.debug("Starting IPC server...")
            ipc.init()
        except ipc.IPCError as e:
            text = ('{}\n\nMaybe another instance is running but '
                    'frozen?'.format(e))
            msgbox = QMessageBox(QMessageBox.Critical, "Error while "
                                 "connecting to running instance!", text)
            msgbox.exec_()
            # We didn't really initialize much so far, so we just quit hard.
            sys.exit(1)

        log.init.debug("Starting init...")
        self.setQuitOnLastWindowClosed(False)
        self.setOrganizationName("qutebrowser")
        self.setApplicationName("qutebrowser")
        self.setApplicationVersion(qutebrowser.__version__)
        self._init_icon()
        utils.actute_warning()
        try:
            self._init_modules()
        except (OSError, UnicodeDecodeError) as e:
            msgbox = QMessageBox(
                QMessageBox.Critical, "Error while initializing!",
                "Error while initializing: {}".format(e))
            msgbox.exec_()
            sys.exit(1)
        QTimer.singleShot(0, self._open_pages)

        log.init.debug("Initializing eventfilter...")
        self._event_filter = modeman.EventFilter(self)
        self.installEventFilter(self._event_filter)

        log.init.debug("Connecting signals...")
        self._connect_signals()

        log.init.debug("Applying python hacks...")
        self._python_hacks()

        QDesktopServices.setUrlHandler('http', self.open_desktopservices_url)
        QDesktopServices.setUrlHandler('https', self.open_desktopservices_url)
        QDesktopServices.setUrlHandler('qute', self.open_desktopservices_url)

        log.init.debug("Init done!")

        if self._crashdlg is not None:
            self._crashdlg.raise_()

    def __repr__(self):
        return utils.get_repr(self)

    def _init_modules(self):
        """Initialize all 'modules' which need to be initialized."""
        log.init.debug("Initializing readline-bridge...")
        readline_bridge = readline.ReadlineBridge()
        objreg.register('readline-bridge', readline_bridge)

        log.init.debug("Initializing directories...")
        standarddir.init()
        log.init.debug("Initializing config...")
        config.init(self._args)
        log.init.debug("Initializing crashlog...")
        self._handle_segfault()
        log.init.debug("Initializing js-bridge...")
        js_bridge = qutescheme.JSBridge(self)
        objreg.register('js-bridge', js_bridge)
        log.init.debug("Initializing websettings...")
        websettings.init()
        log.init.debug("Initializing adblock...")
        host_blocker = adblock.HostBlocker()
        host_blocker.read_hosts()
        objreg.register('host-blocker', host_blocker)
        log.init.debug("Initializing quickmarks...")
        quickmark_manager = quickmarks.QuickmarkManager()
        objreg.register('quickmark-manager', quickmark_manager)
        log.init.debug("Initializing proxy...")
        proxy.init()
        log.init.debug("Initializing cookies...")
        cookie_jar = cookies.CookieJar(self)
        objreg.register('cookie-jar', cookie_jar)
        log.init.debug("Initializing cache...")
        diskcache = cache.DiskCache(self)
        objreg.register('cache', diskcache)
        log.init.debug("Initializing main window...")
        win_id = mainwindow.MainWindow.spawn(
            False if self._args.nowindow else True)
        main_window = objreg.get('main-window', scope='window', window=win_id)
        self.setActiveWindow(main_window)

    def _init_icon(self):
        """Initialize the icon of qutebrowser."""
        icon = QIcon()
        for size in (16, 24, 32, 48, 64, 96, 128, 256, 512):
            filename = ':/icons/qutebrowser-{}x{}.png'.format(size, size)
            pixmap = QPixmap(filename)
            qtutils.ensure_not_null(pixmap)
            icon.addPixmap(pixmap)
        qtutils.ensure_not_null(icon)
        self.setWindowIcon(icon)

    def _handle_segfault(self):
        """Handle a segfault from a previous run."""
        path = standarddir.get(QStandardPaths.DataLocation)
        logname = os.path.join(path, 'crash.log')
        try:
            # First check if an old logfile exists.
            if os.path.exists(logname):
                with open(logname, 'r', encoding='ascii') as f:
                    data = f.read()
                os.remove(logname)
                self._init_crashlogfile()
                if data:
                    # Crashlog exists and has data in it, so something crashed
                    # previously.
                    self._crashdlg = crashdialog.get_fatal_crash_dialog(
                        self._args.debug, data)
                    self._crashdlg.show()
            else:
                # There's no log file, so we can use this to display crashes to
                # the user on the next start.
                self._init_crashlogfile()
        except OSError:
            log.init.exception("Error while handling crash log file!")
            self._init_crashlogfile()

    def _init_crashlogfile(self):
        """Start a new logfile and redirect faulthandler to it."""
        path = standarddir.get(QStandardPaths.DataLocation)
        logname = os.path.join(path, 'crash.log')
        try:
            self._crashlogfile = open(logname, 'w', encoding='ascii')
        except OSError:
            log.init.exception("Error while opening crash log file!")
        else:
            earlyinit.init_faulthandler(self._crashlogfile)

    def _open_pages(self):
        """Open startpage etc. and process commandline args."""
        self.process_args(self._args.command)
        self._open_startpage()
        self._open_quickstart()

    def _get_window(self, via_ipc, force_window=False, force_tab=False):
        """Helper function for process_args to get a window id.

        Args:
            via_ipc: Whether the request was made via IPC.
            force_window: Whether to force opening in a window.
            force_tab: Whether to force opening in a tab.
        """
        if force_window and force_tab:
            raise ValueError("force_window and force_tab are mutually "
                             "exclusive!")
        if not via_ipc:
            # Initial main window
            return 0
        window_to_raise = None
        open_target = config.get('general', 'new-instance-open-target')
        if (open_target == 'window' or force_window) and not force_tab:
            win_id = mainwindow.MainWindow.spawn()
            window = objreg.get('main-window', scope='window', window=win_id)
            window_to_raise = window
        else:
            try:
                window = objreg.last_window()
            except objreg.NoWindow:
                # There is no window left, so we open a new one
                win_id = mainwindow.MainWindow.spawn()
                window = objreg.get('main-window', scope='window',
                                    window=win_id)
                window_to_raise = window
            win_id = window.win_id
            if open_target != 'tab-silent':
                window_to_raise = window
        if window_to_raise is not None:
            window_to_raise.setWindowState(window.windowState() &
                                           ~Qt.WindowMinimized |
                                           Qt.WindowActive)
            window_to_raise.raise_()
            window_to_raise.activateWindow()
            self.alert(window_to_raise)
        return win_id

    def process_args(self, args, via_ipc=False, cwd=None):
        """Process commandline args.

        URLs to open have no prefix, commands to execute begin with a colon.

        Args:
            args: A list of arguments to process.
            via_ipc: Whether the arguments were transmitted over IPC.
            cwd: The cwd to use for fuzzy_url.
        """
        if ipc and not args:
            win_id = self._get_window(via_ipc, force_window=True)
            self._open_startpage(win_id)
            return
        win_id = None
        for cmd in args:
            if cmd.startswith(':'):
                if win_id is None:
                    win_id = self._get_window(via_ipc, force_tab=True)
                log.init.debug("Startup cmd {}".format(cmd))
                commandrunner = runners.CommandRunner(win_id)
                commandrunner.run_safely_init(cmd.lstrip(':'))
            elif not cmd:
                log.init.debug("Empty argument")
                win_id = self._get_window(via_ipc, force_window=True)
            else:
                win_id = self._get_window(via_ipc)
                tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                            window=win_id)
                log.init.debug("Startup URL {}".format(cmd))
                try:
                    url = urlutils.fuzzy_url(cmd, cwd, relative=True)
                except urlutils.FuzzyUrlError as e:
                    message.error(0, "Error in startup argument '{}': "
                                     "{}".format(cmd, e))
                else:
                    tabbed_browser.tabopen(url)

    def _open_startpage(self, win_id=None):
        """Open startpage.

        The startpage is never opened if the given windows are not empty.

        Args:
            win_id: If None, open startpage in all empty windows.
                    If set, open the startpage in the given window.
        """
        if win_id is not None:
            window_ids = [win_id]
        else:
            window_ids = objreg.window_registry
        for cur_win_id in window_ids:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=cur_win_id)
            if tabbed_browser.count() == 0:
                log.init.debug("Opening startpage")
                for urlstr in config.get('general', 'startpage'):
                    try:
                        url = urlutils.fuzzy_url(urlstr)
                    except urlutils.FuzzyUrlError as e:
                        message.error(0, "Error when opening startpage: "
                                         "{}".format(e))
                        tabbed_browser.tabopen(QUrl('about:blank'))
                    else:
                        tabbed_browser.tabopen(url)

    def _open_quickstart(self):
        """Open quickstart if it's the first start."""
        state_config = objreg.get('state-config')
        try:
            quickstart_done = state_config['general']['quickstart-done'] == '1'
        except KeyError:
            quickstart_done = False
        if not quickstart_done:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window='last-focused')
            tabbed_browser.tabopen(
                QUrl('http://www.qutebrowser.org/quickstart.html'))
            try:
                state_config.add_section('general')
            except configparser.DuplicateSectionError:
                pass
            state_config['general']['quickstart-done'] = '1'

    def _python_hacks(self):
        """Get around some PyQt-oddities by evil hacks.

        This sets up the uncaught exception hook, quits with an appropriate
        exit status, and handles Ctrl+C properly by passing control to the
        Python interpreter once all 500ms.
        """
        signal.signal(signal.SIGINT, self.interrupt)
        signal.signal(signal.SIGTERM, self.interrupt)
        timer = usertypes.Timer(self, 'python_hacks')
        timer.start(500)
        timer.timeout.connect(lambda: None)
        objreg.register('python-hack-timer', timer)

    def _connect_signals(self):
        """Connect all signals to their slots."""
        config_obj = objreg.get('config')
        self.lastWindowClosed.connect(self.shutdown)
        config_obj.style_changed.connect(style.get_stylesheet.cache_clear)
        self.focusChanged.connect(self.on_focus_changed)

    def _get_widgets(self):
        """Get a string list of all widgets."""
        widgets = self.allWidgets()
        widgets.sort(key=lambda e: repr(e))
        return [repr(w) for w in widgets]

    def _get_pyqt_objects(self, lines, obj, depth=0):
        """Recursive method for get_all_objects to get Qt objects."""
        for kid in obj.findChildren(QObject):
            lines.append('    ' * depth + repr(kid))
            self._get_pyqt_objects(lines, kid, depth + 1)

    def get_all_objects(self):
        """Get all children of an object recursively as a string."""
        output = ['']
        widget_lines = self._get_widgets()
        widget_lines = ['    ' + e for e in widget_lines]
        widget_lines.insert(0, "Qt widgets - {} objects".format(
            len(widget_lines)))
        output += widget_lines
        pyqt_lines = []
        self._get_pyqt_objects(pyqt_lines, self)
        pyqt_lines = ['    ' + e for e in pyqt_lines]
        pyqt_lines.insert(0, 'Qt objects - {} objects:'.format(
            len(pyqt_lines)))
        output += pyqt_lines
        output += ['']
        output += objreg.dump_objects()
        return '\n'.join(output)

    def _recover_pages(self, forgiving=False):
        """Try to recover all open pages.

        Called from _exception_hook, so as forgiving as possible.

        Args:
            forgiving: Whether to ignore exceptions.

        Return:
            A list containing a list for each window, which in turn contain the
            opened URLs.
        """
        pages = []
        for win_id in objreg.window_registry:
            win_pages = []
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            for tab in tabbed_browser.widgets():
                try:
                    urlstr = tab.cur_url.toString(
                        QUrl.RemovePassword | QUrl.FullyEncoded)
                    if urlstr:
                        win_pages.append(urlstr)
                except Exception:  # pylint: disable=broad-except
                    if forgiving:
                        log.destroy.exception("Error while recovering tab")
                    else:
                        raise
            pages.append(win_pages)
        return pages

    def _save_geometry(self):
        """Save the window geometry to the state config."""
        if self.geometry is not None:
            state_config = objreg.get('state-config')
            geom = base64.b64encode(self.geometry).decode('ASCII')
            try:
                state_config.add_section('geometry')
            except configparser.DuplicateSectionError:
                pass
            state_config['geometry']['mainwindow'] = geom

    def _save_version(self):
        """Save the current version to the state config."""
        state_config = objreg.get('state-config')
        try:
            state_config.add_section('general')
        except configparser.DuplicateSectionError:
            pass
        state_config['general']['version'] = qutebrowser.__version__

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
        try:
            self._crashlogfile.close()
            os.remove(self._crashlogfile.name)
        except OSError:
            log.destroy.exception("Could not remove crash log!")

    def _exception_hook(self, exctype, excvalue, tb):  # noqa
        """Handle uncaught python exceptions.

        It'll try very hard to write all open tabs to a file, and then exit
        gracefully.
        """
        # pylint: disable=broad-except

        exc = (exctype, excvalue, tb)

        if not self._quit_status['crash']:
            log.misc.error("ARGH, there was an exception while the crash "
                           "dialog is already shown:", exc_info=exc)
            return

        log.misc.error("Uncaught exception", exc_info=exc)

        is_ignored_exception = (exctype is bdb.BdbQuit or
                                not issubclass(exctype, Exception))

        if is_ignored_exception or self._args.no_crash_dialog:
            # pdb exit, KeyboardInterrupt, ...
            status = 0 if is_ignored_exception else 2
            try:
                self.shutdown(status)
                return
            except Exception:
                log.init.exception("Error while shutting down")
                self.quit()
                return

        self._quit_status['crash'] = False

        try:
            pages = self._recover_pages(forgiving=True)
        except Exception:
            log.destroy.exception("Error while recovering pages")
            pages = []

        try:
            history = objreg.get('command-history')[-5:]
        except Exception:
            log.destroy.exception("Error while getting history: {}")
            history = []

        try:
            objects = self.get_all_objects()
        except Exception:
            log.destroy.exception("Error while getting objects")
            objects = ""

        try:
            objreg.get('ipc-server').ignored = True
        except Exception:
            log.destroy.exception("Error while ignoring ipc")

        try:
            self.lastWindowClosed.disconnect(self.shutdown)
        except TypeError:
            log.destroy.exception("Error while preventing shutdown")
        QApplication.closeAllWindows()
        self._crashdlg = crashdialog.ExceptionCrashDialog(
            self._args.debug, pages, history, exc, objects)
        ret = self._crashdlg.exec_()
        if ret == QDialog.Accepted:  # restore
            self.restart(shutdown=False, pages=pages)
        # We might risk a segfault here, but that's better than continuing to
        # run in some undefined state, so we only do the most needed shutdown
        # here.
        qInstallMessageHandler(None)
        self._destroy_crashlogfile()
        sys.exit(1)

    @cmdutils.register(instance='app', name=['quit', 'q'])
    def quit(self):
        """Quit qutebrowser."""
        QApplication.closeAllWindows()

    def _get_restart_args(self, pages):
        """Get the current working directory and args to relaunch qutebrowser.

        Args:
            pages: The pages to re-open.

        Return:
            An (args, cwd) tuple.
                args: The commandline as a list of strings.
                cwd: The current working directory as a string.
        """
        if os.path.basename(sys.argv[0]) == 'qutebrowser':
            # Launched via launcher script
            args = [sys.argv[0]]
            cwd = None
        elif hasattr(sys, 'frozen'):
            args = [sys.executable]
            cwd = os.path.abspath(os.path.dirname(sys.executable))
        else:
            args = [sys.executable, '-m', 'qutebrowser']
            cwd = os.path.join(os.path.abspath(os.path.dirname(
                               qutebrowser.__file__)), '..')
            if not os.path.isdir(cwd):
                # Probably running from an python egg. Let's fallback to
                # cwd=None and see if that works out.
                # See https://github.com/The-Compiler/qutebrowser/issues/323
                cwd = None
        for arg in sys.argv[1:]:
            if arg.startswith('-'):
                # We only want to preserve options on a restart.
                args.append(arg)
        # Add all open pages so they get reopened.
        page_args = []
        for win in pages:
            page_args.extend(win)
            page_args.append('')
        if page_args:
            args.extend(page_args[:-1])
        log.destroy.debug("args: {}".format(args))
        log.destroy.debug("cwd: {}".format(cwd))
        return args, cwd

    @cmdutils.register(instance='app', ignore_args=True)
    def restart(self, shutdown=True, pages=None):
        """Restart qutebrowser while keeping existing tabs open."""
        if pages is None:
            pages = self._recover_pages()
        log.destroy.debug("sys.executable: {}".format(sys.executable))
        log.destroy.debug("sys.path: {}".format(sys.path))
        log.destroy.debug("sys.argv: {}".format(sys.argv))
        log.destroy.debug("frozen: {}".format(hasattr(sys, 'frozen')))
        # Open a new process and immediately shutdown the existing one
        try:
            args, cwd = self._get_restart_args(pages)
            if cwd is None:
                subprocess.Popen(args)
            else:
                subprocess.Popen(args, cwd=cwd)
        except OSError:
            log.destroy.exception("Failed to restart")
        else:
            if shutdown:
                self.shutdown()

    @cmdutils.register(instance='app', maxsplit=0, debug=True)
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
        except Exception:  # pylint: disable=broad-except
            out = traceback.format_exc()
        qutescheme.pyeval_output = out
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window='last-focused')
        tabbed_browser.openurl(QUrl('qute:pyeval'), newtab=True)

    @cmdutils.register(instance='app')
    def report(self):
        """Report a bug in qutebrowser."""
        pages = self._recover_pages()
        history = objreg.get('command-history')[-5:]
        objects = self.get_all_objects()
        self._crashdlg = crashdialog.ReportDialog(pages, history, objects)
        self._crashdlg.show()

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
        deferrer = False
        for win_id in objreg.window_registry:
            prompter = objreg.get('prompter', None, scope='window',
                                  window=win_id)
            if prompter is not None and prompter.shutdown():
                deferrer = True
        if deferrer:
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

    def _shutdown(self, status):  # noqa
        """Second stage of shutdown."""
        # pylint: disable=too-many-branches, too-many-statements
        # FIXME refactor this
        # https://github.com/The-Compiler/qutebrowser/issues/113
        log.destroy.debug("Stage 2 of shutting down...")
        # Remove eventfilter
        try:
            log.destroy.debug("Removing eventfilter...")
            self.removeEventFilter(self._event_filter)
        except AttributeError:
            pass
        # Close all windows
        QApplication.closeAllWindows()
        # Shut down IPC
        try:
            objreg.get('ipc-server').shutdown()
        except KeyError:
            pass
        # Save everything
        try:
            config_obj = objreg.get('config')
        except KeyError:
            log.destroy.debug("Config not initialized yet, so not saving "
                              "anything.")
        else:
            to_save = []
            if config.get('general', 'auto-save-config'):
                to_save.append(("config", config_obj.save))
                try:
                    key_config = objreg.get('key-config')
                except KeyError:
                    pass
                else:
                    to_save.append(("keyconfig", key_config.save))
            to_save += [("window geometry", self._save_geometry)]
            to_save += [("version", self._save_version)]
            try:
                command_history = objreg.get('command-history')
            except KeyError:
                pass
            else:
                to_save.append(("command history", command_history.save))
            try:
                quickmark_manager = objreg.get('quickmark-manager')
            except KeyError:
                pass
            else:
                to_save.append(("command history", quickmark_manager.save))
            try:
                state_config = objreg.get('state-config')
            except KeyError:
                pass
            else:
                to_save.append(("window geometry", state_config.save))
            try:
                cookie_jar = objreg.get('cookie-jar')
            except KeyError:
                pass
            else:
                to_save.append(("cookies", cookie_jar.save))
            for what, handler in to_save:
                log.destroy.debug("Saving {} (handler: {})".format(
                    what, utils.qualname(handler)))
                try:
                    handler()
                except OSError as e:
                    msgbox = QMessageBox(
                        QMessageBox.Critical, "Error while saving!",
                        "Error while saving {}: {}".format(what, e))
                    msgbox.exec_()
                except AttributeError as e:
                    log.destroy.warning("Could not save {}.".format(what))
                    log.destroy.debug(e)
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

    def on_focus_changed(self, _old, new):
        """Register currently focused main window in the object registry."""
        if new is None:
            window = None
        else:
            window = new.window()
        if window is None or not isinstance(window, mainwindow.MainWindow):
            try:
                objreg.delete('last-focused-main-window')
            except KeyError:
                pass
        else:
            objreg.register('last-focused-main-window', window, update=True)

    @pyqtSlot(QUrl)
    def open_desktopservices_url(self, url):
        """Handler to open an URL via QDesktopServices."""
        win_id = self._get_window(via_ipc=True, force_window=False)
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)
        tabbed_browser.tabopen(url)

    def exit(self, status):
        """Extend QApplication::exit to log the event."""
        log.destroy.debug("Now calling QApplication::exit.")
        if self._args.debug_exit:
            print("Now logging late shutdown.", file=sys.stderr)
            debug.trace_lines(True)
        super().exit(status)
