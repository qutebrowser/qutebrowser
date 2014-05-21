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

"""Functions to execute an userscript."""

import os
import os.path
import logging
import tempfile
from select import select

from PyQt5.QtCore import (pyqtSignal, QObject, QThread, QStandardPaths,
                          QProcessEnvironment, QProcess)

import qutebrowser.utils.message as message
from qutebrowser.utils.misc import get_standard_dir


class _BlockingFIFOReader(QObject):

    """A worker which reads commands from a FIFO endlessly."""

    got_line = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.fifo = None

    def read(self):
        # We open as R/W so we never get EOF and have to reopen the pipe.
        # See http://www.outflux.net/blog/archives/2008/03/09/using-select-on-a-fifo/
        # We also use os.open and os.fdopen rather than built-in open so we can
        # add O_NONBLOCK.
        fd = os.open(self.filename, os.O_RDWR | os.O_NONBLOCK)
        self.fifo = os.fdopen(fd, 'r')
        while True:
            logging.debug("thread loop")
            ready_r, _ready_w, _ready_e = select([self.fifo], [], [], 1)
            if ready_r:
                logging.debug("reading data")
                for line in self.fifo:
                    self.got_line.emit(line.rstrip())
            if QThread.currentThread().isInterruptionRequested():
                # FIXME this only exists since Qt 5.2, is that an issue?
                self.finished.emit()
                return


class _AbstractUserscriptRunner(QObject):

    got_cmd = pyqtSignal(str)

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

    def __init__(self):
        super().__init__()
        self.filepath = None
        self.proc = None

    def _run_process(self, cmd, *args, env):
        self.proc = QProcess()
        procenv = QProcessEnvironment.systemEnvironment()
        procenv.insert('QUTE_FIFO', self.filepath)
        if env is not None:
            for k, v in env.items():
                procenv.insert(k, v)
        self.proc.setProcessEnvironment(procenv)
        self.proc.error.connect(self.on_proc_error)
        self.proc.finished.connect(self.on_proc_finished)
        self.proc.start(cmd, args)

    def _cleanup(self):
        try:
            os.remove(self.filepath)
        except PermissionError:
            message.error("Failed to delete tempfile...")

    def run(self, cmd, *args, env=None):
        raise NotImplementedError

    def on_proc_finished(self):
        raise NotImplementedError

    def on_proc_error(self, error):
        msg = self.PROCESS_MESSAGES[error]
        message.error("Error while calling userscript: {}".format(msg))


class _POSIXUserscriptRunner(_AbstractUserscriptRunner):

    def __init__(self):
        super().__init__()
        self.reader = None
        self.thread = None
        self.proc = None

    def run(self, cmd, *args, env=None):
        rundir = get_standard_dir(QStandardPaths.RuntimeLocation)
        # tempfile.mktemp is deprecated and discouraged, but we use it here to
        # create a FIFO since the only other alternative would be to create a
        # directory and place the FIFO there, which sucks. Since os.kfifo will
        # raise an exception anyways when the path doesn't exist, it shouldn't
        # be a big issue.
        self.filepath = tempfile.mktemp(prefix='userscript-', dir=rundir)
        os.mkfifo(self.filepath)

        self.reader = _BlockingFIFOReader(self.filepath)
        self.thread = QThread()
        self.reader.moveToThread(self.thread)
        self.reader.got_line.connect(self.got_cmd)
        self.thread.started.connect(self.reader.read)
        self.reader.finished.connect(self.on_reader_finished)
        self.thread.finished.connect(self.on_thread_finished)

        self._run_process(cmd, *args, env=env)
        self.thread.start()

    def on_proc_finished(self):
        logging.debug("proc finished")
        self.thread.requestInterruption()

    def on_proc_error(self, error):
        super().on_proc_error(error)
        self.thread.requestInterruption()

    def on_reader_finished(self):
        logging.debug("reader finished")
        self.thread.quit()
        self.reader.fifo.close()
        self.reader.deleteLater()
        super()._cleanup()

    def on_thread_finished(self):
        logging.debug("thread finished")
        self.thread.deleteLater()


class _WindowsUserscriptRunner(_AbstractUserscriptRunner):

    def __init__(self):
        super().__init__()
        self.oshandle = None
        self.proc = None

    def _cleanup(self):
        """Clean up temporary files after the userscript finished."""
        os.close(self.oshandle)
        super()._cleanup()
        self.oshandle = None
        self.proc = None

    def on_proc_finished(self):
        logging.debug("proc finished")
        with open(self.filepath, 'r') as f:
            for line in f:
                self.got_cmd.emit(line.rstrip())
        self._cleanup()

    def on_proc_error(self, error):
        super().on_proc_error(error)
        self._cleanup()

    def run(self, cmd, *args, env=None):
        self.oshandle, self.filepath = tempfile.mkstemp(text=True)
        self._run_process(cmd, *args, env=env)


class _DummyUserscriptRunner:

    def run(self, _cmd, *_args, _env=None):
        message.error("Userscripts are not supported on this platform!")


class UserscriptRunner(QObject):

    got_cmd = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        if os.name == 'posix':
            self.runner = _POSIXUserscriptRunner()
        elif os.name == 'nt':
            self.runner = _WindowsUserscriptRunner()
        else:
            self.runner = _DummyUserscriptRunner()
        self.runner.got_cmd.connect(self.got_cmd)

    def run(self, *args, **kwargs):
        return self.runner.run(*args, **kwargs)
