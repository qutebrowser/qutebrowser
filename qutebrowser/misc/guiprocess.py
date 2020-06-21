# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import locale
import shlex

from PyQt5.QtCore import (pyqtSlot, pyqtSignal, QObject, QProcess,
                          QProcessEnvironment)

from qutebrowser.utils import message, log
from qutebrowser.browser import qutescheme


class GUIProcess(QObject):

    """An external process which shows notifications in the GUI.

    Args:
        cmd: The command which was started.
        args: A list of arguments which gets passed.
        verbose: Whether to show more messages.
        _output_messages: Show output as messages.
        _started: Whether the underlying process is started.
        _proc: The underlying QProcess.
        _what: What kind of thing is spawned (process/editor/userscript/...).
               Used in messages.

    Signals:
        error/finished/started signals proxied from QProcess.
    """

    error = pyqtSignal(QProcess.ProcessError)
    finished = pyqtSignal(int, QProcess.ExitStatus)
    started = pyqtSignal()

    def __init__(self, what, *, verbose=False, additional_env=None,
                 output_messages=False, parent=None):
        super().__init__(parent)
        self._what = what
        self.verbose = verbose
        self._output_messages = output_messages
        self._started = False
        self.cmd = None
        self.args = None

        self._proc = QProcess(self)
        self._proc.errorOccurred.connect(self._on_error)
        self._proc.errorOccurred.connect(self.error)  # type: ignore[arg-type]
        self._proc.finished.connect(self._on_finished)
        self._proc.finished.connect(self.finished)  # type: ignore[arg-type]
        self._proc.started.connect(self._on_started)
        self._proc.started.connect(self.started)  # type: ignore[arg-type]

        if additional_env is not None:
            procenv = QProcessEnvironment.systemEnvironment()
            for k, v in additional_env.items():
                procenv.insert(k, v)
            self._proc.setProcessEnvironment(procenv)

    @pyqtSlot()
    def _on_error(self):
        """Show a message if there was an error while spawning."""
        msg = self._proc.errorString()
        message.error("Error while spawning {}: {}".format(self._what, msg))

    @pyqtSlot(int, QProcess.ExitStatus)
    def _on_finished(self, code, status):
        """Show a message when the process finished."""
        self._started = False
        log.procs.debug("Process finished with code {}, status {}.".format(
            code, status))

        encoding = locale.getpreferredencoding(do_setlocale=False)
        stderr = self._proc.readAllStandardError().data().decode(
            encoding, 'replace')
        stdout = self._proc.readAllStandardOutput().data().decode(
            encoding, 'replace')

        if self._output_messages:
            if stdout:
                message.info(stdout.strip())
            if stderr:
                message.error(stderr.strip())

        if status == QProcess.CrashExit:
            exitinfo = "{} crashed!".format(self._what.capitalize())
            message.error(exitinfo)
        elif status == QProcess.NormalExit and code == 0:
            exitinfo = "{} exited successfully.".format(
                self._what.capitalize())
            if self.verbose:
                message.info(exitinfo)
        else:
            assert status == QProcess.NormalExit
            # We call this 'status' here as it makes more sense to the user -
            # it's actually 'code'.
            exitinfo = ("{} exited with status {}, see :messages for "
                        "details.").format(self._what.capitalize(), code)
            message.error(exitinfo)

            if stdout:
                log.procs.error("Process stdout:\n" + stdout.strip())
            if stderr:
                log.procs.error("Process stderr:\n" + stderr.strip())

        qutescheme.spawn_output = self._spawn_format(exitinfo, stdout, stderr)

    def _spawn_format(self, exitinfo, stdout, stderr):
        """Produce a formatted string for spawn output."""
        stdout = (stdout or "(No output)").strip()
        stderr = (stderr or "(No output)").strip()

        spawn_string = ("{}\n"
                        "\nProcess stdout:\n {}"
                        "\nProcess stderr:\n {}").format(exitinfo,
                                                         stdout, stderr)
        return spawn_string

    @pyqtSlot()
    def _on_started(self):
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
            message.info('Executing: ' + fake_cmdline)

    def start(self, cmd, args):
        """Convenience wrapper around QProcess::start."""
        log.procs.debug("Starting process.")
        self._pre_start(cmd, args)
        self._proc.start(cmd, args)
        self._proc.closeWriteChannel()

    def start_detached(self, cmd, args):
        """Convenience wrapper around QProcess::startDetached."""
        log.procs.debug("Starting detached.")
        self._pre_start(cmd, args)
        ok, _pid = self._proc.startDetached(
            cmd, args, None)  # type: ignore[call-arg]

        if not ok:
            message.error("Error while spawning {}".format(self._what))
            return False

        log.procs.debug("Process started.")
        self._started = True
        return True

    def exit_status(self):
        return self._proc.exitStatus()
