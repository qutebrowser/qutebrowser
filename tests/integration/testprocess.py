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

import pytestqt.plugin  # pylint: disable=import-error
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QProcess, QObject


class InvalidLine(Exception):

    """Raised when the process prints a line which is not parsable."""

    pass


class Process(QObject):

    """Abstraction over a running test subprocess process.

    Reads the log from its stdout and parses it.

    Signals:
        new_data: Emitted when a new line was parsed.
    """

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

    @pyqtSlot()
    def read_log(self):
        """Read the log from the process' stdout."""
        while self.proc.canReadLine():
            line = self.proc.readLine()
            line = bytes(line).decode('utf-8').rstrip('\r\n')
            print(line)

            try:
                parsed = self._parse_line(line)
            except InvalidLine:
                self._invalid = True
                print("INVALID: {}".format(line))
                continue

            print('parsed: {}'.format(parsed))
            if parsed is not None:
                self._data.append(parsed)
                self.new_data.emit(parsed)

    def start(self):
        """Start the process and wait until it started."""
        blocker = pytestqt.plugin.SignalBlocker(timeout=5000, raising=True)
        blocker.connect(self.ready)
        with blocker:
            self._start()

    def _start(self):
        """Actually start the process."""
        executable, args = self._executable_args()
        self.proc.start(executable, args)
        ok = self.proc.waitForStarted()
        assert ok
        self.proc.readyRead.connect(self.read_log)

    def after_test(self):
        """Clean up data after each test.

        Also checks self._invalid so the test counts as failed if there were
        unexpected output lines earlier.
        """
        self._data.clear()
        if self._invalid:
            raise InvalidLine

    def cleanup(self):
        """Clean up and shut down the process."""
        self.proc.terminate()
        self.proc.waitForFinished()
