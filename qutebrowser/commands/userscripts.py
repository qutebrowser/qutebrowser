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

"""Functions to execute an userscript."""

import os
import os.path
import tempfile

from PyQt5.QtCore import (pyqtSignal, pyqtSlot, QObject, QSocketNotifier,
                          QProcessEnvironment, QProcess)

from qutebrowser.utils import message, log, objreg, standarddir
from qutebrowser.commands import runners, cmdexc
from qutebrowser.config import config


class _QtFIFOReader(QObject):

    """A FIFO reader based on a QSocketNotifier."""

    got_line = pyqtSignal(str)

    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self._filepath = filepath
        # We open as R/W so we never get EOF and have to reopen the pipe.
        # See http://www.outflux.net/blog/archives/2008/03/09/using-select-on-a-fifo/
        # We also use os.open and os.fdopen rather than built-in open so we
        # can add O_NONBLOCK.
        fd = os.open(filepath, os.O_RDWR |
                     os.O_NONBLOCK)  # pylint: disable=no-member
        self.fifo = os.fdopen(fd, 'r')
        self._notifier = QSocketNotifier(fd, QSocketNotifier.Read, self)
        self._notifier.activated.connect(self.read_line)

    @pyqtSlot()
    def read_line(self):
        """(Try to) read a line from the FIFO."""
        log.procs.debug("QSocketNotifier triggered!")
        self._notifier.setEnabled(False)
        for line in self.fifo:
            self.got_line.emit(line.rstrip('\r\n'))
        self._notifier.setEnabled(True)

    def cleanup(self):
        """Clean up so the FIFO can be closed."""
        self._notifier.setEnabled(False)


class _BaseUserscriptRunner(QObject):

    """Common part between the Windows and the POSIX userscript runners.

    Attributes:
        _filepath: The path of the file/FIFO which is being read.
        _proc: The QProcess which is being executed.
        _win_id: The window ID this runner is associated with.

    Class attributes:
        PROCESS_MESSAGES: A mapping of QProcess::ProcessError members to
                          human-readable error strings.

    Signals:
        got_cmd: Emitted when a new command arrived and should be executed.
        finished: Emitted when the userscript finished running.
    """

    got_cmd = pyqtSignal(str)
    finished = pyqtSignal()

    PROCESS_MESSAGES = {
        QProcess.FailedToStart: "The process failed to start.",
        QProcess.Crashed: "The process crashed.",
        QProcess.Timedout: "The last waitFor...() function timed out.",
        QProcess.WriteError: ("An error occurred when attempting to write to "
                              "the process."),
        QProcess.ReadError: ("An error occurred when attempting to read from "
                             "the process."),
        QProcess.UnknownError: "An unknown error occurred.",
    }

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self._filepath = None
        self._proc = None

    def _run_process(self, cmd, *args, env):
        """Start the given command via QProcess.

        Args:
            cmd: The command to be started.
            *args: The arguments to hand to the command
            env: A dictionary of environment variables to add.
        """
        self._proc = QProcess(self)
        procenv = QProcessEnvironment.systemEnvironment()
        procenv.insert('QUTE_FIFO', self._filepath)
        if env is not None:
            for k, v in env.items():
                procenv.insert(k, v)
        self._proc.setProcessEnvironment(procenv)
        self._proc.error.connect(self.on_proc_error)
        self._proc.finished.connect(self.on_proc_finished)
        self._proc.start(cmd, args)

    def _cleanup(self):
        """Clean up the temporary file."""
        log.procs.debug("Deleting temporary file {}.".format(self._filepath))
        try:
            os.remove(self._filepath)
        except OSError as e:
            # NOTE: Do not replace this with "raise CommandError" as it's
            # executed async.
            message.error(self._win_id,
                          "Failed to delete tempfile... ({})".format(e))
        self._filepath = None
        self._proc = None

    def run(self, cmd, *args, env=None):
        """Run the userscript given.

        Needs to be overridden by superclasses.

        Args:
            cmd: The command to be started.
            *args: The arguments to hand to the command
            env: A dictionary of environment variables to add.
        """
        raise NotImplementedError

    def on_proc_finished(self):
        """Called when the process has finished.

        Needs to be overridden by superclasses.
        """
        raise NotImplementedError

    def on_proc_error(self, error):
        """Called when the process encountered an error."""
        msg = self.PROCESS_MESSAGES[error]
        # NOTE: Do not replace this with "raise CommandError" as it's
        # executed async.
        message.error(self._win_id,
                      "Error while calling userscript: {}".format(msg))
        log.procs.debug("Userscript process error: {} - {}".format(error, msg))


class _POSIXUserscriptRunner(_BaseUserscriptRunner):

    """Userscript runner to be used on POSIX. Uses _QtFIFOReader.

    Commands are executed immediately when they arrive in the FIFO.

    Attributes:
        _reader: The _QtFIFOReader instance.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(win_id, parent)
        self._reader = None

    def run(self, cmd, *args, env=None):
        try:
            # tempfile.mktemp is deprecated and discouraged, but we use it here
            # to create a FIFO since the only other alternative would be to
            # create a directory and place the FIFO there, which sucks. Since
            # os.mkfifo will raise an exception anyways when the path doesn't
            # exist, it shouldn't be a big issue.
            self._filepath = tempfile.mktemp(prefix='qutebrowser-userscript-',
                                             dir=standarddir.runtime())
            os.mkfifo(self._filepath)  # pylint: disable=no-member
        except OSError as e:
            message.error(self._win_id, "Error while creating FIFO: {}".format(
                e))
            return

        self._reader = _QtFIFOReader(self._filepath)
        self._reader.got_line.connect(self.got_cmd)

        self._run_process(cmd, *args, env=env)

    def on_proc_finished(self):
        """Interrupt the reader when the process finished."""
        log.procs.debug("Userscript process finished.")
        self.finish()

    def on_proc_error(self, error):
        """Interrupt the reader when the process had an error."""
        super().on_proc_error(error)
        self.finish()

    def finish(self):
        """Quit the thread and clean up when the reader finished."""
        log.procs.debug("Cleaning up")
        self._reader.cleanup()
        self._reader.fifo.close()
        self._reader.deleteLater()
        self._reader = None
        super()._cleanup()
        self.finished.emit()


class _WindowsUserscriptRunner(_BaseUserscriptRunner):

    """Userscript runner to be used on Windows.

    This is a much more dumb implementation compared to POSIXUserscriptRunner.
    It uses a normal flat file for commands and executes them all at once when
    the process has finished, as Windows doesn't really understand the concept
    of using files as named pipes.

    This also means the userscript *has* to use >> (append) rather than >
    (overwrite) to write to the file!

    Attributes:
        _oshandle: The oshandle of the temp file.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(win_id, parent)
        self._oshandle = None

    def _cleanup(self):
        """Clean up temporary files after the userscript finished."""
        try:
            os.close(self._oshandle)
        except OSError:
            log.procs.exception("Failed to close file handle!")
        super()._cleanup()
        self._oshandle = None

    def on_proc_finished(self):
        """Read back the commands when the process finished."""
        log.procs.debug("Userscript process finished.")
        try:
            with open(self._filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    self.got_cmd.emit(line.rstrip())
        except OSError:
            log.procs.exception("Failed to read command file!")
        self._cleanup()
        self.finished.emit()

    def on_proc_error(self, error):
        """Clean up when the process had an error."""
        super().on_proc_error(error)
        self._cleanup()
        self.finished.emit()

    def run(self, cmd, *args, env=None):
        try:
            self._oshandle, self._filepath = tempfile.mkstemp(text=True)
        except OSError as e:
            message.error(self._win_id, "Error while creating tempfile: "
                                        "{}".format(e))
            return
        self._run_process(cmd, *args, env=env)


class _DummyUserscriptRunner:

    """Simple dummy runner which displays an error when using userscripts.

    Used on unknown systems since we don't know what (or if any) approach will
    work there.

    Signals:
        finished: Always emitted.
    """

    finished = pyqtSignal()

    def run(self, _cmd, *_args, _env=None):
        """Print an error as userscripts are not supported."""
        self.finished.emit()
        raise cmdexc.CommandError(
            "Userscripts are not supported on this platform!")


# Here we basically just assign a generic UserscriptRunner class which does the
# right thing depending on the platform.
if os.name == 'posix':
    UserscriptRunner = _POSIXUserscriptRunner
elif os.name == 'nt':
    UserscriptRunner = _WindowsUserscriptRunner
else:
    UserscriptRunner = _DummyUserscriptRunner


def run(cmd, *args, win_id, env):
    """Convenience method to run an userscript.

    Args:
        cmd: The userscript binary to run.
        *args: The arguments to pass to the userscript.
        win_id: The window id the userscript is executed in.
        env: A dictionary of variables to add to the process environment.
    """
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)
    commandrunner = runners.CommandRunner(win_id, tabbed_browser)
    runner = UserscriptRunner(win_id, tabbed_browser)
    runner.got_cmd.connect(
        lambda cmd: log.commands.debug("Got userscript command: {}".format(
            cmd)))
    runner.got_cmd.connect(commandrunner.run_safely)
    user_agent = config.get('network', 'user-agent')
    if user_agent is not None:
        env['QUTE_USER_AGENT'] = user_agent
    runner.run(cmd, *args, env=env)
    runner.finished.connect(commandrunner.deleteLater)
    runner.finished.connect(runner.deleteLater)
