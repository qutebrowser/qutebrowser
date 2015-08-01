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

# pylint: disable=protected-access

"""Tests for qutebrowser.misc.guiprocess."""

import sys
import textwrap

import pytest
from PyQt5.QtCore import QProcess

from qutebrowser.misc import guiprocess


# FIXME check statusbar messages


def _py_proc(code):
    """Get a python executable and args list which executes the given code."""
    return (sys.executable, ['-c', textwrap.dedent(code.strip('\n'))])


@pytest.fixture(autouse=True)
def mock_modules(monkeypatch, stubs):
    monkeypatch.setattr('qutebrowser.misc.guiprocess.message',
                        stubs.MessageModule())


@pytest.yield_fixture()
def proc(qtbot):
    """A fixture providing a GUIProcess and cleaning it up after the test."""
    p = guiprocess.GUIProcess(0, 'test')
    yield p
    if p._proc.state() == QProcess.Running:
        with qtbot.waitSignal(p.finished, timeout=10000) as blocker:
            p._proc.terminate()
        if not blocker.signal_triggered:
            p._proc.kill()


@pytest.fixture()
def fake_proc(monkeypatch, stubs):
    """A fixture providing a GUIProcess with a mocked QProcess."""
    p = guiprocess.GUIProcess(0, 'test')
    monkeypatch.setattr(p, '_proc', stubs.fake_qprocess())
    return p


@pytest.mark.not_frozen
def test_start(proc, qtbot):
    """Test simply starting a process."""
    with qtbot.waitSignals([proc.started, proc.finished], raising=True,
                           timeout=10000):
        argv = _py_proc("import sys; print('test'); sys.exit(0)")
        proc.start(*argv)

    assert bytes(proc._proc.readAll()).rstrip() == b'test'


@pytest.mark.parametrize('argv', [
    pytest.mark.not_frozen(_py_proc('import sys; sys.exit(0)')),
    ('does_not', 'exist'),
])
def test_start_detached(fake_proc, argv):
    """Test starting a detached process."""
    fake_proc._proc.startDetached.return_value = (True, 0)
    fake_proc.start_detached(*argv)
    fake_proc._proc.startDetached.assert_called_with(*list(argv) + [None])


@pytest.mark.not_frozen
def test_double_start(qtbot, proc):
    """Test starting a GUIProcess twice."""
    with qtbot.waitSignal(proc.started, raising=True, timeout=10000):
        argv = _py_proc("import time; time.sleep(10)")
        proc.start(*argv)
    with pytest.raises(ValueError):
        proc.start('', [])


@pytest.mark.not_frozen
def test_double_start_finished(qtbot, proc):
    """Test starting a GUIProcess twice (with the first call finished)."""
    with qtbot.waitSignals([proc.started, proc.finished], raising=True,
                           timeout=10000):
        argv = _py_proc("import sys; sys.exit(0)")
        proc.start(*argv)
    with qtbot.waitSignals([proc.started, proc.finished], raising=True,
                           timeout=10000):
        argv = _py_proc("import sys; sys.exit(0)")
        proc.start(*argv)


def test_cmd_args(fake_proc):
    """Test the cmd and args attributes."""
    cmd = 'does_not_exist'
    args = ['arg1', 'arg2']
    fake_proc.start(cmd, args)
    assert (fake_proc.cmd, fake_proc.args) == (cmd, args)


def test_error(qtbot, proc):
    """Test the process emitting an error."""
    with qtbot.waitSignal(proc.error, raising=True):
        proc.start('this_does_not_exist_either', [])


@pytest.mark.not_frozen
def test_exit_unsuccessful(qtbot, proc):
    with qtbot.waitSignal(proc.finished, raising=True, timeout=10000):
        proc.start(*_py_proc('import sys; sys.exit(0)'))
