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
        return testprocess.Line(line)

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
        pyproc.code = "time.sleep(0.5); print('foobar')"
        with stopwatch(min_ms=500):
            pyproc.start()
            pyproc.wait_for(data="foobar")

    def test_other_text(self, pyproc):
        """Test wait_for when getting some unrelated text."""
        pyproc.code = "time.sleep(0.1); print('blahblah')"
        pyproc.start()
        with pytest.raises(testprocess.WaitForTimeout):
            pyproc.wait_for(data="foobar", timeout=500)

    def test_no_text(self, pyproc):
        """Test wait_for when getting no text at all."""
        pyproc.code = "pass"
        pyproc.start()
        with pytest.raises(testprocess.WaitForTimeout):
            pyproc.wait_for(data="foobar", timeout=100)

    @pytest.mark.parametrize('message', ['foobar', 'literal [x]'])
    def test_existing_message(self, message, pyproc):
        """Test with a message which already passed when waiting."""
        pyproc.code = "print('{}')".format(message)
        pyproc.start()
        time.sleep(0.5)  # to make sure the message is printed
        pyproc.wait_for(data=message)

    def test_existing_message_previous_test(self, pyproc):
        """Make sure the message of a previous test gets ignored."""
        pyproc.code = "print('foobar')"
        pyproc.start()
        line = pyproc.wait_for(data="foobar")
        line.waited_for = False  # so we don't test what the next test does
        pyproc.after_test()
        with pytest.raises(testprocess.WaitForTimeout):
            pyproc.wait_for(data="foobar", timeout=100)

    def test_existing_message_already_waited(self, pyproc):
        """Make sure an existing message doesn't stop waiting twice.

        wait_for checks existing messages (see above), but we don't want it to
        automatically proceed if we already *did* use wait_for on one of the
        existing messages, as that makes it likely it's not what we actually
        want.
        """
        pyproc.code = "time.sleep(0.1); print('foobar')"
        pyproc.start()
        pyproc.wait_for(data="foobar")
        with pytest.raises(testprocess.WaitForTimeout):
            pyproc.wait_for(data="foobar", timeout=100)
