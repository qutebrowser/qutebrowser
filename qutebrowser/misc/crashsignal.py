# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Handlers for crashes and OS signals."""

import os
import sys
import bdb
import pdb  # flake8: disable=T002
import signal
import functools
import faulthandler
import os.path
import collections

from PyQt5.QtCore import (pyqtSlot, qInstallMessageHandler, QObject,
                          QSocketNotifier, QTimer, QUrl)
from PyQt5.QtWidgets import QApplication, QDialog

from qutebrowser.commands import cmdutils
from qutebrowser.misc import earlyinit, crashdialog
from qutebrowser.utils import usertypes, standarddir, log, objreg, debug


ExceptionInfo = collections.namedtuple('ExceptionInfo',
                                       'pages, cmd_history, objects')


# Used by mainwindow.py to skip confirm questions on crashes
is_crashing = False


class CrashHandler(QObject):

    """Handler for crashes, reports and exceptions.

    Attributes:
        _app: The QApplication instance.
        _quitter: The Quitter instance.
        _args: The argparse namespace.
        _crash_dialog: The CrashDialog currently being shown.
        _crash_log_file: The file handle for the faulthandler crash log.
    """

    def __init__(self, *, app, quitter, args, parent=None):
        super().__init__(parent)
        self._app = app
        self._quitter = quitter
        self._args = args
        self._crash_log_file = None
        self._crash_dialog = None

    def activate(self):
        """Activate the exception hook."""
        sys.excepthook = self.exception_hook

    def handle_segfault(self):
        """Handle a segfault from a previous run."""
        logname = os.path.join(standarddir.data(), 'crash.log')
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
                    self._crash_dialog = crashdialog.get_fatal_crash_dialog(
                        self._args.debug, data)
                    self._crash_dialog.show()
            else:
                # There's no log file, so we can use this to display crashes to
                # the user on the next start.
                self._init_crashlogfile()
        except OSError:
            log.init.exception("Error while handling crash log file!")
            self._init_crashlogfile()

    def _recover_pages(self, forgiving=False):
        """Try to recover all open pages.

        Called from exception_hook, so as forgiving as possible.

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
                    urlstr = tab.url().toString(
                        QUrl.RemovePassword | QUrl.FullyEncoded)
                    if urlstr:
                        win_pages.append(urlstr)
                except Exception:
                    if forgiving:
                        log.destroy.exception("Error while recovering tab")
                    else:
                        raise
            pages.append(win_pages)
        return pages

    def _init_crashlogfile(self):
        """Start a new logfile and redirect faulthandler to it."""
        assert not self._args.no_err_windows
        logname = os.path.join(standarddir.data(), 'crash.log')
        try:
            self._crash_log_file = open(logname, 'w', encoding='ascii')
        except OSError:
            log.init.exception("Error while opening crash log file!")
        else:
            earlyinit.init_faulthandler(self._crash_log_file)

    @cmdutils.register(instance='crash-handler')
    def report(self):
        """Report a bug in qutebrowser."""
        pages = self._recover_pages()
        cmd_history = objreg.get('command-history')[-5:]
        objects = debug.get_all_objects()
        self._crash_dialog = crashdialog.ReportDialog(pages, cmd_history,
                                                      objects)
        self._crash_dialog.show()

    def destroy_crashlogfile(self):
        """Clean up the crash log file and delete it."""
        if self._crash_log_file is None:
            return
        # We use sys.__stderr__ instead of sys.stderr here so this will still
        # work when sys.stderr got replaced, e.g. by "Python Tools for Visual
        # Studio".
        if sys.__stderr__ is not None:
            faulthandler.enable(sys.__stderr__)
        else:
            faulthandler.disable()
        try:
            self._crash_log_file.close()
            os.remove(self._crash_log_file.name)
        except OSError:
            log.destroy.exception("Could not remove crash log!")

    def _get_exception_info(self):
        """Get info needed for the exception hook/dialog.

        Return:
            An ExceptionInfo namedtuple.
        """
        try:
            pages = self._recover_pages(forgiving=True)
        except Exception:
            log.destroy.exception("Error while recovering pages")
            pages = []

        try:
            cmd_history = objreg.get('command-history')[-5:]
        except Exception:
            log.destroy.exception("Error while getting history: {}")
            cmd_history = []

        try:
            objects = debug.get_all_objects()
        except Exception:
            log.destroy.exception("Error while getting objects")
            objects = ""
        return ExceptionInfo(pages, cmd_history, objects)

    def exception_hook(self, exctype, excvalue, tb):
        """Handle uncaught python exceptions.

        It'll try very hard to write all open tabs to a file, and then exit
        gracefully.
        """
        exc = (exctype, excvalue, tb)
        qapp = QApplication.instance()

        if not self._quitter.quit_status['crash']:
            log.misc.error("ARGH, there was an exception while the crash "
                           "dialog is already shown:", exc_info=exc)
            return

        log.misc.error("Uncaught exception", exc_info=exc)

        is_ignored_exception = (exctype is bdb.BdbQuit or
                                not issubclass(exctype, Exception))

        if self._args.pdb_postmortem:
            pdb.post_mortem(tb)

        if is_ignored_exception or self._args.pdb_postmortem:
            # pdb exit, KeyboardInterrupt, ...
            status = 0 if is_ignored_exception else 2
            try:
                self._quitter.shutdown(status)
                return
            except Exception:
                log.init.exception("Error while shutting down")
                qapp.quit()
                return

        self._quitter.quit_status['crash'] = False
        info = self._get_exception_info()

        try:
            objreg.get('ipc-server').ignored = True
        except Exception:
            log.destroy.exception("Error while ignoring ipc")

        try:
            self._app.lastWindowClosed.disconnect(
                self._quitter.on_last_window_closed)
        except TypeError:
            log.destroy.exception("Error while preventing shutdown")

        global is_crashing
        is_crashing = True

        self._app.closeAllWindows()
        if self._args.no_err_windows:
            crashdialog.dump_exception_info(exc, info.pages, info.cmd_history,
                                            info.objects)
        else:
            self._crash_dialog = crashdialog.ExceptionCrashDialog(
                self._args.debug, info.pages, info.cmd_history, exc,
                info.objects)
            ret = self._crash_dialog.exec_()
            if ret == QDialog.Accepted:  # restore
                self._quitter.restart(info.pages)

        # We might risk a segfault here, but that's better than continuing to
        # run in some undefined state, so we only do the most needed shutdown
        # here.
        qInstallMessageHandler(None)
        self.destroy_crashlogfile()
        sys.exit(usertypes.Exit.exception)

    def raise_crashdlg(self):
        """Raise the crash dialog if one exists."""
        if self._crash_dialog is not None:
            self._crash_dialog.raise_()


class SignalHandler(QObject):

    """Handler responsible for handling OS signals (SIGINT, SIGTERM, etc.).

    Attributes:
        _app: The QApplication instance.
        _quitter: The Quitter instance.
        _activated: Whether activate() was called.
        _notifier: A QSocketNotifier used for signals on Unix.
        _timer: A QTimer used to poll for signals on Windows.
        _orig_handlers: A {signal: handler} dict of original signal handlers.
        _orig_wakeup_fd: The original wakeup filedescriptor.
    """

    def __init__(self, *, app, quitter, parent=None):
        super().__init__(parent)
        self._app = app
        self._quitter = quitter
        self._notifier = None
        self._timer = usertypes.Timer(self, 'python_hacks')
        self._orig_handlers = {}
        self._activated = False
        self._orig_wakeup_fd = None

    def activate(self):
        """Set up signal handlers.

        On Windows this uses a QTimer to periodically hand control over to
        Python so it can handle signals.

        On Unix, it uses a QSocketNotifier with os.set_wakeup_fd to get
        notified.
        """
        self._orig_handlers[signal.SIGINT] = signal.signal(
            signal.SIGINT, self.interrupt)
        self._orig_handlers[signal.SIGTERM] = signal.signal(
            signal.SIGTERM, self.interrupt)

        if os.name == 'posix' and hasattr(signal, 'set_wakeup_fd'):
            # pylint: disable=import-error,no-member,useless-suppression
            import fcntl
            read_fd, write_fd = os.pipe()
            for fd in [read_fd, write_fd]:
                flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            self._notifier = QSocketNotifier(read_fd, QSocketNotifier.Read,
                                             self)
            self._notifier.activated.connect(self.handle_signal_wakeup)
            self._orig_wakeup_fd = signal.set_wakeup_fd(write_fd)
        else:
            self._timer.start(1000)
            self._timer.timeout.connect(lambda: None)
        self._activated = True

    def deactivate(self):
        """Deactivate all signal handlers."""
        if not self._activated:
            return
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            rfd = self._notifier.socket()
            wfd = signal.set_wakeup_fd(self._orig_wakeup_fd)
            os.close(rfd)
            os.close(wfd)
        for sig, handler in self._orig_handlers.items():
            signal.signal(sig, handler)
        self._timer.stop()
        self._activated = False

    @pyqtSlot()
    def handle_signal_wakeup(self):
        """Handle a newly arrived signal.

        This gets called via self._notifier when there's a signal.

        Python will get control here, so the signal will get handled.
        """
        log.destroy.debug("Handling signal wakeup!")
        self._notifier.setEnabled(False)
        read_fd = self._notifier.socket()
        try:
            os.read(read_fd, 1)
        except OSError:
            log.destroy.exception("Failed to read wakeup fd.")
        self._notifier.setEnabled(True)

    def _log_later(self, *lines):
        """Log the given text line-wise with a QTimer."""
        for line in lines:
            QTimer.singleShot(0, functools.partial(log.destroy.info, line))

    def interrupt(self, signum, _frame):
        """Handler for signals to gracefully shutdown (SIGINT/SIGTERM).

        This calls shutdown and remaps the signal to call
        interrupt_forcefully the next time.
        """
        signal.signal(signal.SIGINT, self.interrupt_forcefully)
        signal.signal(signal.SIGTERM, self.interrupt_forcefully)
        # Signals can arrive anywhere, so we do this in the main thread
        self._log_later("SIGINT/SIGTERM received, shutting down!",
                        "Do the same again to forcefully quit.")
        QTimer.singleShot(0, functools.partial(
            self._quitter.shutdown, 128 + signum))

    def interrupt_forcefully(self, signum, _frame):
        """Interrupt forcefully on the second SIGINT/SIGTERM request.

        This skips our shutdown routine and calls QApplication:exit instead.
        It then remaps the signals to call self.interrupt_really_forcefully the
        next time.
        """
        signal.signal(signal.SIGINT, self.interrupt_really_forcefully)
        signal.signal(signal.SIGTERM, self.interrupt_really_forcefully)
        # Signals can arrive anywhere, so we do this in the main thread
        self._log_later("Forceful quit requested, goodbye cruel world!",
                        "Do the same again to quit with even more force.")
        QTimer.singleShot(0, functools.partial(self._app.exit, 128 + signum))

    def interrupt_really_forcefully(self, signum, _frame):
        """Interrupt with even more force on the third SIGINT/SIGTERM request.

        This doesn't run *any* Qt cleanup and simply exits via Python.
        It will most likely lead to a segfault.
        """
        print("WHY ARE YOU DOING THIS TO ME? :(")
        sys.exit(128 + signum)
