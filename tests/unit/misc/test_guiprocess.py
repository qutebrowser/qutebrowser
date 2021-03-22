# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for qutebrowser.misc.guiprocess."""

import sys
import logging

import pytest
from PyQt5.QtCore import QProcess, QUrl

from qutebrowser.misc import guiprocess
from qutebrowser.utils import usertypes, utils
from qutebrowser.api import cmdutils


@pytest.fixture()
def proc(qtbot, caplog):
    """A fixture providing a GUIProcess and cleaning it up after the test."""
    p = guiprocess.GUIProcess('testprocess')
    yield p
    if p._proc.state() == QProcess.Running:
        with caplog.at_level(logging.ERROR):
            with qtbot.wait_signal(p.finished, timeout=10000,
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


class TestProcessCommand:

    @pytest.fixture
    def tab(self, fake_web_tab):
        return fake_web_tab()

    def test_no_process(self, tab, monkeypatch):
        monkeypatch.setattr(guiprocess, 'last_pid', None)
        with pytest.raises(cmdutils.CommandError, match='No process executed yet!'):
            guiprocess.process(tab)

    def test_last_pid(self, tab, monkeypatch, fake_proc):
        monkeypatch.setattr(guiprocess, 'last_pid', 1234)
        monkeypatch.setitem(guiprocess.all_processes, 1234, fake_proc)

        guiprocess.process(tab)
        assert tab.url() == QUrl('qute://process/1234')

    def test_explicit_pid(self, tab, monkeypatch, fake_proc):
        monkeypatch.setattr(guiprocess, 'last_pid', 1234)
        monkeypatch.setitem(guiprocess.all_processes, 5678, fake_proc)

        guiprocess.process(tab, 5678)
        assert tab.url() == QUrl('qute://process/5678')

    def test_inexistent_pid(self, tab):
        with pytest.raises(
                cmdutils.CommandError, match='No process found with pid 1337'):
            guiprocess.process(tab, 1337)

    def test_terminate(self, tab, monkeypatch, fake_proc):
        monkeypatch.setitem(guiprocess.all_processes, 1234, fake_proc)

        guiprocess.process(tab, 1234, 'terminate')
        fake_proc._proc.terminate.assert_called_with()
        fake_proc._proc.kill.assert_not_called()

    def test_kill(self, tab, monkeypatch, fake_proc):
        monkeypatch.setitem(guiprocess.all_processes, 1234, fake_proc)

        guiprocess.process(tab, 1234, 'kill')
        fake_proc._proc.kill.assert_called_with()
        fake_proc._proc.terminate.assert_not_called()


def test_not_started(proc):
    assert str(proc.outcome) == 'Testprocess did not start.'
    assert proc.outcome.state_str() == 'not started'
    assert not proc.outcome.was_successful()
    assert not proc.outcome.running
    assert proc.outcome.status is None
    assert proc.outcome.code is None


def test_start(proc, qtbot, message_mock, py_proc):
    """Test simply starting a process."""
    with qtbot.wait_signals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        cmd, args = py_proc("import sys; print('test'); sys.exit(0)")
        proc.start(cmd, args)

    assert not message_mock.messages

    assert not proc.outcome.running
    assert proc.outcome.status == QProcess.NormalExit
    assert proc.outcome.code == 0
    assert str(proc.outcome) == 'Testprocess exited successfully.'
    assert proc.outcome.state_str() == 'successful'
    assert proc.outcome.was_successful()


def test_start_verbose(proc, qtbot, message_mock, py_proc):
    """Test starting a process verbosely."""
    proc.verbose = True

    with qtbot.wait_signals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        cmd, args = py_proc("import sys; print('test'); sys.exit(0)")
        proc.start(cmd, args)

    msgs = message_mock.messages
    assert msgs[0].level == usertypes.MessageLevel.info
    assert msgs[1].level == usertypes.MessageLevel.info
    assert msgs[0].text.startswith("Executing:")
    assert msgs[1].text == "Testprocess exited successfully."


@pytest.mark.parametrize('stdout', [True, False])
@pytest.mark.parametrize('stderr', [True, False])
def test_start_output_message(proc, qtbot, caplog, message_mock, py_proc,
                              stdout, stderr):
    proc._output_messages = True

    code = ['import sys']
    if stdout:
        code.append('print("stdout text")')
    if stderr:
        code.append(r'sys.stderr.write("stderr text\n")')
    code.append("sys.exit(0)")

    with caplog.at_level(logging.ERROR, 'message'):
        with qtbot.wait_signals([proc.started, proc.finished],
                               timeout=10000,
                               order='strict'):
            cmd, args = py_proc(';'.join(code))
            proc.start(cmd, args)

    if stdout and stderr:
        stdout_msg = message_mock.messages[0]
        stderr_msg = message_mock.messages[-1]
        msg_count = 3  # stdout is reported twice (once live)
    elif stdout:
        stdout_msg = message_mock.messages[0]
        stderr_msg = None
        msg_count = 2  # stdout is reported twice (once live)
    elif stderr:
        stdout_msg = None
        stderr_msg = message_mock.messages[0]
        msg_count = 1
    else:
        stdout_msg = None
        stderr_msg = None
        msg_count = 0

    assert len(message_mock.messages) == msg_count

    if stdout_msg is not None:
        assert stdout_msg.level == usertypes.MessageLevel.info
        assert stdout_msg.text == 'stdout text'
        assert proc.stdout.strip() == "stdout text", proc.stdout
    if stderr_msg is not None:
        assert stderr_msg.level == usertypes.MessageLevel.error
        assert stderr_msg.text == 'stderr text'
        assert proc.stderr.strip() == "stderr text", proc.stderr


@pytest.mark.parametrize('line1, line2, expected1, expected2', [
    ('First line\n', 'Second line\n', 'First line', 'First line\nSecond line'),
    ('First line', '\rSecond line', 'First line', 'Second line'),
    ('First line\n', '\rSecond line', 'First line', 'First line\nSecond line'),
    (
        'First line\nSecond line\nThird line',
        '\rNew line',
        'First line\nSecond line\nThird line',
        'First line\nSecond line\nNew line',
    ),
    ('First line', 'Second line\rThird line', 'First line', 'Third line'),
])
def test_live_messages_output(qtbot, proc, py_proc, message_mock,
                              line1, line2, expected1, expected2):
    proc._output_messages = True

    cmd, args = py_proc(r"""
        import time, sys
        print(sys.argv[1], flush=True, end='')
        time.sleep(0.5)
        print(sys.argv[2], flush=True, end='')
    """)
    args += [line1, line2]

    with qtbot.wait_signal(proc.finished, timeout=5000):
        proc.start(cmd, args)

    assert len(message_mock.messages) == 3
    assert all(msg.level == usertypes.MessageLevel.info
               for msg in message_mock.messages)

    assert message_mock.messages[0].text == expected1
    assert message_mock.messages[1].text == expected2
    assert message_mock.messages[2].text == expected2


def test_start_env(monkeypatch, qtbot, py_proc):
    monkeypatch.setenv('QUTEBROWSER_TEST_1', '1')
    env = {'QUTEBROWSER_TEST_2': '2'}
    proc = guiprocess.GUIProcess('testprocess', additional_env=env)

    cmd, args = py_proc("""
        import os
        import json
        import sys

        env = dict(os.environ)
        print(json.dumps(env))
        sys.exit(0)
    """)

    with qtbot.wait_signals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        proc.start(cmd, args)

    assert 'QUTEBROWSER_TEST_1' in proc.stdout
    assert 'QUTEBROWSER_TEST_2' in proc.stdout


def test_start_detached(fake_proc):
    """Test starting a detached process."""
    cmd = 'foo'
    args = ['bar']
    fake_proc._proc.startDetached.return_value = (True, 0)
    fake_proc.start_detached(cmd, args)
    fake_proc._proc.startDetached.assert_called_with(cmd, args, None)


def test_start_detached_error(fake_proc, message_mock, caplog):
    """Test starting a detached process with ok=False."""
    cmd = 'foo'
    args = ['bar']
    fake_proc._proc.startDetached.return_value = (False, 0)

    with caplog.at_level(logging.ERROR):
        fake_proc.start_detached(cmd, args)
    msg = message_mock.getmsg(usertypes.MessageLevel.error)
    expected = "Error while spawning testprocess"
    assert msg.text == expected


def test_double_start(qtbot, proc, py_proc):
    """Test starting a GUIProcess twice."""
    with qtbot.wait_signal(proc.started, timeout=10000):
        cmd, args = py_proc("import time; time.sleep(10)")
        proc.start(cmd, args)
    with pytest.raises(ValueError):
        proc.start('', [])


def test_double_start_finished(qtbot, proc, py_proc):
    """Test starting a GUIProcess twice (with the first call finished)."""
    with qtbot.wait_signals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        cmd, args = py_proc("import sys; sys.exit(0)")
        proc.start(cmd, args)
    with qtbot.wait_signals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        cmd, args = py_proc("import sys; sys.exit(0)")
        proc.start(cmd, args)


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


def test_running(qtbot, proc, py_proc):
    """Test proc.outcome while the process is still running."""
    with qtbot.wait_signal(proc.started, timeout=5000):
        proc.start(*py_proc("import time; time.sleep(10)"))
    assert proc.outcome.running
    assert proc.outcome.status is None
    assert proc.outcome.code is None
    assert str(proc.outcome) == 'Testprocess is running.'
    assert proc.outcome.state_str() == 'running'
    assert not proc.outcome.was_successful()


def test_error(qtbot, proc, caplog, message_mock):
    """Test the process emitting an error."""
    with caplog.at_level(logging.ERROR, 'message'):
        with qtbot.wait_signal(proc.error, timeout=5000):
            proc.start('this_does_not_exist_either', [])

    msg = message_mock.getmsg(usertypes.MessageLevel.error)
    assert msg.text.startswith(
        "Testprocess 'this_does_not_exist_either' failed to start:")

    if not utils.is_windows:
        assert msg.text.endswith(
            "(Hint: Make sure 'this_does_not_exist_either' exists and is executable)")

    assert not proc.outcome.running
    assert proc.outcome.status is None
    assert proc.outcome.code is None
    assert str(proc.outcome) == 'Testprocess did not start.'
    assert proc.outcome.state_str() == 'not started'
    assert not proc.outcome.was_successful()


def test_exit_unsuccessful(qtbot, proc, message_mock, py_proc, caplog):
    with caplog.at_level(logging.ERROR):
        with qtbot.wait_signal(proc.finished, timeout=10000):
            proc.start(*py_proc('import sys; sys.exit(1)'))

    msg = message_mock.getmsg(usertypes.MessageLevel.error)
    expected = "Testprocess exited with status 1. See :process for details."
    assert msg.text == expected

    assert not proc.outcome.running
    assert proc.outcome.status == QProcess.NormalExit
    assert proc.outcome.code == 1
    assert str(proc.outcome) == 'Testprocess exited with status 1.'
    assert proc.outcome.state_str() == 'unsuccessful'
    assert not proc.outcome.was_successful()


def test_exit_crash(qtbot, proc, message_mock, py_proc, caplog):
    with caplog.at_level(logging.ERROR):
        with qtbot.wait_signal(proc.finished, timeout=10000):
            proc.start(*py_proc("""
                import os, signal
                os.kill(os.getpid(), signal.SIGSEGV)
            """))

    expected = (
        "Testprocess exited with status 11. See :process for details."
        if utils.is_windows else "Testprocess crashed. See :process for details."
    )
    msg = message_mock.getmsg(usertypes.MessageLevel.error)
    assert msg.text == expected

    assert not proc.outcome.running
    assert proc.outcome.status == QProcess.CrashExit
    assert str(proc.outcome) == 'Testprocess crashed.'
    assert proc.outcome.state_str() == 'crashed'
    assert not proc.outcome.was_successful()


@pytest.mark.parametrize('stream', ['stdout', 'stderr'])
def test_exit_unsuccessful_output(qtbot, proc, caplog, py_proc, stream):
    """When a process fails, its output should be logged."""
    with caplog.at_level(logging.ERROR):
        with qtbot.wait_signal(proc.finished, timeout=10000):
            proc.start(*py_proc(f"""
                import sys
                print("test", file=sys.{stream})
                sys.exit(1)
            """))
    assert caplog.messages[-2] == 'Process {}:\ntest'.format(stream)
    assert caplog.messages[-1] == (
        'Testprocess exited with status 1. See :process for details.')


@pytest.mark.parametrize('stream', ['stdout', 'stderr'])
def test_exit_successful_output(qtbot, proc, py_proc, stream):
    """When a process succeeds, no output should be logged.

    The test doesn't actually check the log as it'd fail because of the error
    logging.
    """
    with qtbot.wait_signal(proc.finished, timeout=10000):
        proc.start(*py_proc("""
            import sys
            print("test", file=sys.{})
            sys.exit(0)
        """.format(stream)))


def test_stdout_not_decodable(proc, qtbot, message_mock, py_proc):
    """Test handling malformed utf-8 in stdout."""
    with qtbot.wait_signals([proc.started, proc.finished], timeout=10000,
                           order='strict'):
        cmd, args = py_proc(r"""
            import sys
            # Using \x81 because it's invalid in UTF-8 and CP1252
            sys.stdout.buffer.write(b"A\x81B")
            sys.exit(0)
            """)
        proc.start(cmd, args)

    assert not message_mock.messages
    assert proc.stdout == "A\ufffdB"


def test_str_unknown(proc):
    assert str(proc) == '<unknown testprocess command>'


def test_str(proc, py_proc):
    proc.start(*py_proc("import sys"))
    assert str(proc) == f"{sys.executable} -c 'import sys'"
