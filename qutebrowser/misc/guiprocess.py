# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""A QProcess which shows notifications in the GUI."""

import shlex

from PyQt5.QtCore import (pyqtSlot, pyqtSignal, QObject, QProcess,
                          QProcessEnvironment)

from qutebrowser.utils import message, log

# A mapping of QProcess::ErrorCode's to human-readable strings.

ERROR_STRINGS = {
    QProcess.FailedToStart: "The process failed to start.",
    QProcess.Crashed: "The process crashed.",
    QProcess.Timedout: "The last waitFor...() function timed out.",
    QProcess.WriteError: ("An error occurred when attempting to write to the "
                          "process."),
    QProcess.ReadError: ("An error occurred when attempting to read from the "
                         "process."),
    QProcess.UnknownError: "An unknown error occurred.",
}


class GUIProcess(QObject):

    """An external process which shows notifications in the GUI.

    Args:
        cmd: The command which was started.
        args: A list of arguments which gets passed.
        verbose: Whether to show more messages.
        _started: Whether the underlying process is started.
        _proc: The underlying QProcess.
        _win_id: The window ID this process is used in.
        _what: What kind of thing is spawned (process/editor/userscript/...).
               Used in messages.

    Signals:
        error/finished/started signals proxied from QProcess.
    """

    error = pyqtSignal(QProcess.ProcessError)
    finished = pyqtSignal(int, QProcess.ExitStatus)
    started = pyqtSignal()

    def __init__(self, win_id, what, *, verbose=False, additional_env=None,
                 parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self._what = what
        self.verbose = verbose
        self._started = False
        self.cmd = None
        self.args = None

        self._proc = QProcess(self)
        self._proc.error.connect(self.on_error)
        self._proc.error.connect(self.error)
        self._proc.finished.connect(self.on_finished)
        self._proc.finished.connect(self.finished)
        self._proc.started.connect(self.on_started)
        self._proc.started.connect(self.started)

        if additional_env is not None:
            procenv = QProcessEnvironment.systemEnvironment()
            for k, v in additional_env.items():
                procenv.insert(k, v)
            self._proc.setProcessEnvironment(procenv)

    @pyqtSlot(QProcess.ProcessError)
    def on_error(self, error):
        """Show a message if there was an error while spawning."""
        msg = ERROR_STRINGS[error]
        message.error(self._win_id, "Error while spawning {}: {}".format(
                      self._what, msg), immediately=True)

    @pyqtSlot(int, QProcess.ExitStatus)
    def on_finished(self, code, status):
        """Show a message when the process finished."""
        self._started = False
        log.procs.debug("Process finished with code {}, status {}.".format(
            code, status))
        if status == QProcess.CrashExit:
            message.error(self._win_id,
                          "{} crashed!".format(self._what.capitalize()),
                          immediately=True)
        elif status == QProcess.NormalExit and code == 0:
            if self.verbose:
                message.info(self._win_id, "{} exited successfully.".format(
                    self._what.capitalize()))
        else:
            assert status == QProcess.NormalExit
            message.error(self._win_id, "{} exited with status {}.".format(
                self._what.capitalize(), code))

    @pyqtSlot()
    def on_started(self):
        """Called when the process started successfully."""
        log.procs.debug("Process started.")
        assert not self._started
        self._started = True

    def _pre_start(self, cmd, args):
        """Prepare starting of a QProcess."""
        if self._started:
            raise ValueError("Trying to start a running QProcess!")
        self.cmd = cmd
        self.args = args
        fake_cmdline = ' '.join(shlex.quote(e) for e in [cmd] + list(args))
        log.procs.debug("Executing: {}".format(fake_cmdline))
        if self.verbose:
            message.info(self._win_id, 'Executing: ' + fake_cmdline)

    def start(self, cmd, args, mode=None):
        """Convenience wrapper around QProcess::start."""
        log.procs.debug("Starting process.")
        self._pre_start(cmd, args)
        if mode is None:
            self._proc.start(cmd, args)
        else:
            self._proc.start(cmd, args, mode)

    def start_detached(self, cmd, args, cwd=None):
        """Convenience wrapper around QProcess::startDetached."""
        log.procs.debug("Starting detached.")
        self._pre_start(cmd, args)
        ok, _pid = self._proc.startDetached(cmd, args, cwd)

        if ok:
            log.procs.debug("Process started.")
            self._started = True
        else:
            message.error(self._win_id, "Error while spawning {}: {}.".format(
                          self._what, self._proc.error()), immediately=True)
