# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.misc.guiprocess."""

import logging

import pytest
from PyQt5.QtCore import QProcess, QIODevice

from qutebrowser.misc import guiprocess
from qutebrowser.utils import usertypes
from qutebrowser.browser import qutescheme


@pytest.fixture()
def proc(qtbot, caplog):
    """A fixture providing a GUIProcess and cleaning it up after the test."""
    p = guiprocess.GUIProcess('testprocess')
    yield p
    if p._proc.state() == QProcess.Running:
        with caplog.at_level(logging.ERROR):
            with qtbot.waitSignal(p.finished, timeout=10000,
                                  raising=False) as blocker:
                p._proc.terminate()
            if not blocker.signal_triggered:
                p._proc.kill()
            p._proc.waitForFinished()


@pytest.fixture()
def fake_proc(monkeypatch, stubs):
    """A fixture providing a GUIProcess with a mocked QProcess."""
    p = guiprocess.GUIProcess('testprocess')
    monkeypatch.setattr(p, '_proc', stubs.fake_qprocess())
    return p


def test_start(proc, qtbot, message_mock, py_proc):
    """Test simply starting a process."""
    with qtbot.waitSignals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        argv = py_proc("import sys; print('test'); sys.exit(0)")
        proc.start(*argv)

    assert not message_mock.messages
    assert qutescheme.spawn_output == proc._spawn_format(stdout="test")


def test_start_verbose(proc, qtbot, message_mock, py_proc):
    """Test starting a process verbosely."""
    proc.verbose = True

    with qtbot.waitSignals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        argv = py_proc("import sys; print('test'); sys.exit(0)")
        proc.start(*argv)

    msgs = message_mock.messages
    assert msgs[0].level == usertypes.MessageLevel.info
    assert msgs[1].level == usertypes.MessageLevel.info
    assert msgs[0].text.startswith("Executing:")
    assert msgs[1].text == "Testprocess exited successfully."
    assert qutescheme.spawn_output == proc._spawn_format(stdout="test")


def test_start_env(monkeypatch, qtbot, py_proc):
    monkeypatch.setenv('QUTEBROWSER_TEST_1', '1')
    env = {'QUTEBROWSER_TEST_2': '2'}
    proc = guiprocess.GUIProcess('testprocess', additional_env=env)

    argv = py_proc("""
        import os
        import json
        import sys

        env = dict(os.environ)
        print(json.dumps(env))
        sys.exit(0)
    """)

    with qtbot.waitSignals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        proc.start(*argv)

    data = qutescheme.spawn_output
    assert 'QUTEBROWSER_TEST_1' in data
    assert 'QUTEBROWSER_TEST_2' in data


@pytest.mark.qt_log_ignore('QIODevice::read.*: WriteOnly device')
def test_start_mode(proc, qtbot, py_proc):
    """Test simply starting a process with mode parameter."""
    with qtbot.waitSignals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        argv = py_proc("import sys; print('test'); sys.exit(0)")
        proc.start(*argv, mode=QIODevice.NotOpen)

    assert not proc._proc.readAll()


def test_start_detached(fake_proc):
    """Test starting a detached process."""
    argv = ['foo', 'bar']
    fake_proc._proc.startDetached.return_value = (True, 0)
    fake_proc.start_detached(*argv)
    fake_proc._proc.startDetached.assert_called_with(*list(argv) + [None])


def test_start_detached_error(fake_proc, message_mock, caplog):
    """Test starting a detached process with ok=False."""
    argv = ['foo', 'bar']
    fake_proc._proc.startDetached.return_value = (False, 0)
    fake_proc._proc.error.return_value = QProcess.FailedToStart
    with caplog.at_level(logging.ERROR):
        fake_proc.start_detached(*argv)
    msg = message_mock.getmsg(usertypes.MessageLevel.error)
    expected = ("Error while spawning testprocess: The process failed to "
                "start.")
    assert msg.text == expected


def test_double_start(qtbot, proc, py_proc):
    """Test starting a GUIProcess twice."""
    with qtbot.waitSignal(proc.started, timeout=10000):
        argv = py_proc("import time; time.sleep(10)")
        proc.start(*argv)
    with pytest.raises(ValueError):
        proc.start('', [])


def test_double_start_finished(qtbot, proc, py_proc):
    """Test starting a GUIProcess twice (with the first call finished)."""
    with qtbot.waitSignals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        argv = py_proc("import sys; sys.exit(0)")
        proc.start(*argv)
    with qtbot.waitSignals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        argv = py_proc("import sys; sys.exit(0)")
        proc.start(*argv)


def test_cmd_args(fake_proc):
    """Test the cmd and args attributes."""
    cmd = 'does_not_exist'
    args = ['arg1', 'arg2']
    fake_proc.start(cmd, args)
    assert (fake_proc.cmd, fake_proc.args) == (cmd, args)


def test_start_logging(fake_proc, caplog):
    """Make sure that starting logs the executed commandline."""
    cmd = 'does_not_exist'
    args = ['arg', 'arg with spaces']
    with caplog.at_level(logging.DEBUG):
        fake_proc.start(cmd, args)
    assert caplog.messages == [
        "Starting process.",
        "Executing: does_not_exist arg 'arg with spaces'"
    ]


def test_error(qtbot, proc, caplog, message_mock):
    """Test the process emitting an error."""
    with caplog.at_level(logging.ERROR, 'message'):
        with qtbot.waitSignal(proc.error, timeout=5000):
            proc.start('this_does_not_exist_either', [])

    msg = message_mock.getmsg(usertypes.MessageLevel.error)
    expected_msg = ("Error while spawning testprocess: The process failed to "
                    "start.")
    assert msg.text == expected_msg


def test_exit_unsuccessful(qtbot, proc, message_mock, py_proc, caplog):
    with caplog.at_level(logging.ERROR):
        with qtbot.waitSignal(proc.finished, timeout=10000):
            proc.start(*py_proc('import sys; sys.exit(1)'))

    msg = message_mock.getmsg(usertypes.MessageLevel.error)
    expected = "Testprocess exited with status 1, see :messages for details."
    assert msg.text == expected


@pytest.mark.parametrize('stream', ['stdout', 'stderr'])
def test_exit_unsuccessful_output(qtbot, proc, caplog, py_proc, stream):
    """When a process fails, its output should be logged."""
    with caplog.at_level(logging.ERROR):
        with qtbot.waitSignal(proc.finished, timeout=10000):
            proc.start(*py_proc("""
                import sys
                print("test", file=sys.{})
                sys.exit(1)
            """.format(stream)))
    assert caplog.messages[-1] == 'Process {}:\ntest'.format(stream)


@pytest.mark.parametrize('stream', ['stdout', 'stderr'])
def test_exit_successful_output(qtbot, proc, py_proc, stream):
    """When a process succeeds, no output should be logged.

    The test doesn't actually check the log as it'd fail because of the error
    logging.
    """
    with qtbot.waitSignal(proc.finished, timeout=10000):
        proc.start(*py_proc("""
            import sys
            print("test", file=sys.{})
            sys.exit(0)
        """.format(stream)))


def test_stdout_not_decodable(proc, qtbot, message_mock, py_proc):
    """Test handling malformed utf-8 in stdout."""
    with qtbot.waitSignals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        argv = py_proc(r"""
            import sys
            # Using \x81 because it's invalid in UTF-8 and CP1252
            sys.stdout.buffer.write(b"A\x81B")
            sys.exit(0)
            """)
        proc.start(*argv)
    assert not message_mock.messages
    assert qutescheme.spawn_output == proc._spawn_format(stdout="A\ufffdB")
