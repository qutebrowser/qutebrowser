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
import select

from PyQt5.QtCore import (pyqtSignal, QObject, QThread, QStandardPaths,
                          QProcessEnvironment, QProcess, QUrl)

from qutebrowser.utils import message, log, objreg, standarddir
from qutebrowser.commands import runners, cmdexc


class _BlockingFIFOReader(QObject):

    """A worker which reads commands from a FIFO endlessly.

    This is intended to be run in a separate QThread. It reads from the given
    FIFO even across EOF so an userscript can write to it multiple times.

    It uses select() so it can timeout once per second, checking if termination
    was requested.

    Attributes:
        _filepath: The filename of the FIFO to read.
        fifo: The file object which is being read.

    Signals:
        got_line: Emitted when a new line arrived.
        finished: Emitted when the read loop realized it should terminate and
                  is about to do so.
    """

    got_line = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self._filepath = filepath
        self.fifo = None

    def read(self):
        """Blocking read loop which emits got_line when a new line arrived."""
        try:
            # We open as R/W so we never get EOF and have to reopen the pipe.
            # See http://www.outflux.net/blog/archives/2008/03/09/using-select-on-a-fifo/
            # We also use os.open and os.fdopen rather than built-in open so we
            # can add O_NONBLOCK.
            fd = os.open(self._filepath, os.O_RDWR |
                         os.O_NONBLOCK)  # pylint: disable=no-member
            self.fifo = os.fdopen(fd, 'r')
        except OSError:
            log.procs.exception("Failed to read FIFO")
            self.finished.emit()
            return
        while True:
            log.procs.debug("thread loop")
            ready_r, _ready_w, _ready_e = select.select([self.fifo], [], [], 1)
            if ready_r:
                log.procs.debug("reading data")
                for line in self.fifo:
                    self.got_line.emit(line.rstrip())
            if QThread.currentThread().isInterruptionRequested():
                self.finished.emit()
                return


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


class _POSIXUserscriptRunner(_BaseUserscriptRunner):

    """Userscript runner to be used on POSIX. Uses _BlockingFIFOReader.

    The OS must have support for named pipes and select(). Commands are
    executed immediately when they arrive in the FIFO.

    Attributes:
        _reader: The _BlockingFIFOReader instance.
        _thread: The QThread where reader runs.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(win_id, parent)
        self._reader = None
        self._thread = None

    def run(self, cmd, *args, env=None):
        rundir = standarddir.get(QStandardPaths.RuntimeLocation)
        try:
            # tempfile.mktemp is deprecated and discouraged, but we use it here
            # to create a FIFO since the only other alternative would be to
            # create a directory and place the FIFO there, which sucks. Since
            # os.kfifo will raise an exception anyways when the path doesn't
            # exist, it shouldn't be a big issue.
            self._filepath = tempfile.mktemp(prefix='userscript-', dir=rundir)
            os.mkfifo(self._filepath)  # pylint: disable=no-member
        except OSError as e:
            message.error(self._win_id, "Error while creating FIFO: {}".format(
                e))
            return

        self._reader = _BlockingFIFOReader(self._filepath)
        self._thread = QThread(self)
        self._reader.moveToThread(self._thread)
        self._reader.got_line.connect(self.got_cmd)
        self._thread.started.connect(self._reader.read)
        self._reader.finished.connect(self.on_reader_finished)
        self._thread.finished.connect(self.on_thread_finished)

        self._run_process(cmd, *args, env=env)
        self._thread.start()

    def on_proc_finished(self):
        """Interrupt the reader when the process finished."""
        log.procs.debug("proc finished")
        self._thread.requestInterruption()

    def on_proc_error(self, error):
        """Interrupt the reader when the process had an error."""
        super().on_proc_error(error)
        self._thread.requestInterruption()

    def on_reader_finished(self):
        """Quit the thread and clean up when the reader finished."""
        log.procs.debug("reader finished")
        self._thread.quit()
        self._reader.fifo.close()
        self._reader.deleteLater()
        super()._cleanup()
        self.finished.emit()

    def on_thread_finished(self):
        """Clean up the QThread object when the thread finished."""
        log.procs.debug("thread finished")
        self._thread.deleteLater()


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
        log.procs.debug("proc finished")
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


def run(cmd, *args, url, win_id):
    """Convenience method to run an userscript."""
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)
    # We don't remove the password in the URL here, as it's probably safe to
    # pass via env variable..
    urlstr = url.toString(QUrl.FullyEncoded)
    commandrunner = runners.CommandRunner(win_id, tabbed_browser)
    runner = UserscriptRunner(win_id, tabbed_browser)
    runner.got_cmd.connect(commandrunner.run_safely)
    runner.run(cmd, *args, env={'QUTE_URL': urlstr})
    runner.finished.connect(commandrunner.deleteLater)
    runner.finished.connect(runner.deleteLater)
