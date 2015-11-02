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

"""Base class for a subprocess run for tests.."""

import re
import fnmatch

import pytestqt.plugin  # pylint: disable=import-error
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QProcess, QObject, QElapsedTimer
from PyQt5.QtTest import QSignalSpy


class InvalidLine(Exception):

    """Raised when the process prints a line which is not parsable."""

    pass


class ProcessExited(Exception):

    """Raised when the child process did exit."""

    pass


class WaitForTimeout(Exception):

    """Raised when wait_for didn't get the expected message."""


class Process(QObject):

    """Abstraction over a running test subprocess process.

    Reads the log from its stdout and parses it.

    Signals:
        ready: Emitted when the server finished starting up.
        new_data: Emitted when a new line was parsed.
    """

    ready = pyqtSignal()
    new_data = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._invalid = False
        self._data = []
        self.proc = QProcess()
        self.proc.setReadChannel(QProcess.StandardError)

    def _parse_line(self, line):
        """Parse the given line from the log.

        Return:
            A self.ParseResult member.
        """
        raise NotImplementedError

    def _executable_args(self):
        """Get the executable and arguments to pass to it as a tuple."""
        raise NotImplementedError

    def _get_data(self):
        """Get the parsed data for this test.

        Also waits for 0.5s to make sure any new data is received.

        Subprocesses are expected to alias this to a public method with a
        better name.
        """
        self.proc.waitForReadyRead(500)
        self.read_log()
        return self._data

    def _wait_signal(self, signal, timeout=5000, raising=True):
        """Wait for a signal to be emitted.

        Should be used in a contextmanager.
        """
        blocker = pytestqt.plugin.SignalBlocker(
            timeout=timeout, raising=raising)
        blocker.connect(signal)
        return blocker

    @pyqtSlot()
    def read_log(self):
        """Read the log from the process' stdout."""
        if not hasattr(self, 'proc'):
            # I have no idea how this happens, but it does...
            return
        while self.proc.canReadLine():
            line = self.proc.readLine()
            line = bytes(line).decode('utf-8', errors='ignore').rstrip('\r\n')

            try:
                parsed = self._parse_line(line)
            except InvalidLine:
                self._invalid = True
                print("INVALID: {}".format(line))
                continue

            if parsed is not None:
                self._data.append(parsed)
                self.new_data.emit(parsed)

    def start(self):
        """Start the process and wait until it started."""
        with self._wait_signal(self.ready, timeout=30000):
            self._start()

    def _start(self):
        """Actually start the process."""
        executable, args = self._executable_args()
        self.proc.readyRead.connect(self.read_log)
        self.proc.start(executable, args)
        ok = self.proc.waitForStarted()
        assert ok
        assert self.is_running()

    def after_test(self):
        """Clean up data after each test.

        Also checks self._invalid so the test counts as failed if there were
        unexpected output lines earlier.
        """
        self._data.clear()
        if self._invalid:
            raise InvalidLine

    def terminate(self):
        """Clean up and shut down the process."""
        if not self.is_running():
            raise ProcessExited
        self.proc.terminate()
        self.proc.waitForFinished()

    def is_running(self):
        """Check if the process is currently running."""
        return self.proc.state() == QProcess.Running

    def wait_for(self, timeout=5000, **kwargs):
        """Wait until a given value is found in the data.

        Keyword arguments to this function get interpreted as attributes of the
        searched data. Every given argument is treated as a pattern which
        the attribute has to match against.

        The behavior of this method is slightly different depending on the
        types of the filtered values:

        - If the value is a string or bytes object and the expected value is
          too, the pattern is treated as a fnmatch glob pattern.
        - If the value is a string or bytes object and the expected value is a
          compiled regex, it is used for matching.
        - If the value is any other type, == is used.

        Return:
            The matched line.
        """

        # FIXME make this a context manager which inserts a marker in
        # self._data in __enter__ and checks if the signal already did arrive
        # after marker in __exit__, and if not, waits?

        regex_type = type(re.compile(''))

        spy = QSignalSpy(self.new_data)
        elapsed_timer = QElapsedTimer()
        elapsed_timer.start()

        while True:
            got_signal = spy.wait(timeout)
            if not got_signal or elapsed_timer.hasExpired(timeout):
                raise WaitForTimeout

            for args in spy:
                assert len(args) == 1
                line = args[0]

                matches = []

                for key, expected in kwargs.items():
                    if expected is None:
                        continue

                    value = getattr(line, key)

                    if isinstance(expected, regex_type):
                        matches.append(expected.match(value))
                    elif isinstance(value, (bytes, str)):
                        matches.append(fnmatch.fnmatchcase(value, expected))
                    else:
                        matches.append(value == expected)

                if all(matches):
                    return line
