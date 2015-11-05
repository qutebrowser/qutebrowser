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

"""Test testprocess.Process."""

import sys
import time
import contextlib
import datetime

import pytest
from PyQt5.QtCore import QProcess

import testprocess

pytestmark = [pytest.mark.not_frozen]


@contextlib.contextmanager
def stopwatch(min_ms=None, max_ms=None):
    if min_ms is None and max_ms is None:
        raise ValueError("Using stopwatch with both min_ms/max_ms None does "
                         "nothing.")
    start = datetime.datetime.now()
    yield
    stop = datetime.datetime.now()
    delta_ms = (stop - start).total_seconds() * 1000
    if min_ms is not None:
        assert delta_ms >= min_ms
    if max_ms is not None:
        assert delta_ms <= max_ms


class Line:

    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return 'Line({!r})'.format(self.data)


class PythonProcess(testprocess.Process):

    """A testprocess which runs the given Python code."""

    def __init__(self):
        super().__init__()
        self.proc.setReadChannel(QProcess.StandardOutput)
        self.code = None

    def _parse_line(self, line):
        print("LINE: {}".format(line))
        if line.strip() == 'ready':
            self.ready.emit()
        return Line(line)

    def _executable_args(self):
        code = [
            'import sys, time',
            'print("ready")',
            'sys.stdout.flush()',
            self.code,
            'sys.stdout.flush()',
            'time.sleep(20)',
        ]
        return (sys.executable, ['-c', ';'.join(code)])


class TestWaitFor:

    @pytest.yield_fixture
    def pyproc(self):
        proc = PythonProcess()
        yield proc
        proc.terminate()

    def test_successful(self, pyproc):
        """Using wait_for with the expected text."""
        pyproc.code = "import time; time.sleep(0.5); print('foobar')"
        pyproc.start()
        with stopwatch(min_ms=300):  # on Windows, this can be done faster...
            pyproc.wait_for(data="foobar")

    def test_other_text(self, pyproc):
        """Test wait_for when getting some unrelated text."""
        pyproc.code = "import time; time.sleep(0.1); print('blahblah')"
        pyproc.start()
        with pytest.raises(testprocess.WaitForTimeout):
            pyproc.wait_for(data="foobar", timeout=500)

    def test_no_text(self, pyproc):
        """Test wait_for when getting no text at all."""
        pyproc.code = "pass"
        pyproc.start()
        with pytest.raises(testprocess.WaitForTimeout):
            pyproc.wait_for(data="foobar", timeout=100)

    def test_existing_message(self, pyproc):
        """Test with a message which already passed when waiting."""
        pyproc.code = "print('foobar')"
        pyproc.start()
        time.sleep(0.5)  # to make sure the message is printed
        pyproc.wait_for(data="foobar")

    def test_existing_message_previous_test(self, pyproc):
        """Make sure the message of a previous test gets ignored."""
        pyproc.code = "print('foobar')"
        pyproc.start()
        time.sleep(0.5)  # to make sure the message is printed
        pyproc.after_test()
        with pytest.raises(testprocess.WaitForTimeout):
            pyproc.wait_for(data="foobar", timeout=100)
