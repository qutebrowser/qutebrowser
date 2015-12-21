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

import os
import json
import time
import logging
import signal

import pytest
from PyQt5.QtCore import QFileSystemWatcher

from qutebrowser.commands import userscripts, cmdexc


@pytest.fixture(autouse=True)
def guiprocess_message_mock(message_mock):
    message_mock.patch('qutebrowser.misc.guiprocess.message')
    return message_mock


@pytest.mark.posix
class TestQtFIFOReader:

    @pytest.yield_fixture
    def reader(self, tmpdir, qapp):
        fifo_path = str(tmpdir / 'fifo')
        os.mkfifo(fifo_path)
        reader = userscripts._QtFIFOReader(fifo_path)
        yield reader
        if reader._notifier.isEnabled():
            reader.cleanup()

    def test_single_line(self, reader, qtbot):
        """Test QSocketNotifier with a single line of data."""
        with qtbot.waitSignal(reader.got_line) as blocker:
            with open(reader._filepath, 'w', encoding='utf-8') as f:
                f.write('foobar\n')

        assert blocker.args == ['foobar']

    def test_cleanup(self, reader):
        assert not reader._fifo.closed
        reader.cleanup()
        assert reader._fifo.closed


@pytest.fixture(params=[
    userscripts._POSIXUserscriptRunner,
    userscripts._WindowsUserscriptRunner,
])
def runner(request):
    if (os.name != 'posix' and
            request.param is userscripts._POSIXUserscriptRunner):
        pytest.skip("Requires a POSIX os")
    else:
        return request.param(0)


def test_command(qtbot, py_proc, runner):
    cmd, args = py_proc(r"""
        import os
        with open(os.environ['QUTE_FIFO'], 'w') as f:
            f.write('foo\n')
    """)
    with qtbot.waitSignal(runner.got_cmd, raising=True,
                          timeout=10000) as blocker:
        runner.run(cmd, *args)
    assert blocker.args == ['foo']


def test_custom_env(qtbot, monkeypatch, py_proc, runner):
    monkeypatch.setenv('QUTEBROWSER_TEST_1', '1')
    env = {'QUTEBROWSER_TEST_2': '2'}

    cmd, args = py_proc(r"""
        import os
        import json

        env = dict(os.environ)

        with open(os.environ['QUTE_FIFO'], 'w') as f:
            json.dump(env, f)
            f.write('\n')
    """)

    with qtbot.waitSignal(runner.got_cmd, raising=True,
                          timeout=10000) as blocker:
        runner.run(cmd, *args, env=env)

    data = blocker.args[0]
    ret_env = json.loads(data)
    assert 'QUTEBROWSER_TEST_1' in ret_env
    assert 'QUTEBROWSER_TEST_2' in ret_env


def test_temporary_files(qtbot, tmpdir, py_proc, runner):
    """Make sure temporary files are passed and cleaned up correctly."""
    text_file = tmpdir / 'text'
    text_file.write('This is text')
    html_file = tmpdir / 'html'
    html_file.write('This is HTML')

    env = {'QUTE_TEXT': str(text_file), 'QUTE_HTML': str(html_file)}

    cmd, args = py_proc(r"""
        import os
        import json

        data = {'html': None, 'text': None}

        with open(os.environ['QUTE_HTML'], 'r') as f:
            data['html'] = f.read()

        with open(os.environ['QUTE_TEXT'], 'r') as f:
            data['text'] = f.read()

        with open(os.environ['QUTE_FIFO'], 'w') as f:
            json.dump(data, f)
            f.write('\n')
    """)

    with qtbot.waitSignal(runner.finished, raising=True, timeout=10000):
        with qtbot.waitSignal(runner.got_cmd, raising=True,
                              timeout=10000) as blocker:
            runner.run(cmd, *args, env=env)

    data = blocker.args[0]
    parsed = json.loads(data)
    assert parsed['text'] == 'This is text'
    assert parsed['html'] == 'This is HTML'

    assert not text_file.exists()
    assert not html_file.exists()


def test_command_with_error(qtbot, tmpdir, py_proc, runner):
    text_file = tmpdir / 'text'
    text_file.write('This is text')

    env = {'QUTE_TEXT': str(text_file)}
    cmd, args = py_proc(r"""
        import sys
        sys.exit(1)
    """)

    with qtbot.waitSignal(runner.finished, raising=True, timeout=10000):
        runner.run(cmd, *args, env=env)

    assert not text_file.exists()


def test_killed_command(qtbot, tmpdir, py_proc, runner):
    text_file = tmpdir / 'text'
    text_file.write('This is text')

    pidfile = tmpdir / 'pid'
    watcher = QFileSystemWatcher()
    watcher.addPath(str(tmpdir))

    env = {'QUTE_TEXT': str(text_file)}
    cmd, args = py_proc(r"""
        import os
        import time
        import sys

        # We can't use QUTE_FIFO to transmit the PID because that wouldn't work
        # on Windows, where QUTE_FIFO is only monitored after the script has
        # exited.

        with open(sys.argv[1], 'w') as f:
            f.write(str(os.getpid()))

        time.sleep(30)
    """)
    args.append(str(pidfile))

    with qtbot.waitSignal(watcher.directoryChanged, raising=True,
                          timeout=10000):
        runner.run(cmd, *args, env=env)

    # Make sure the PID was written to the file, not just the file created
    time.sleep(0.5)

    with qtbot.waitSignal(runner.finished, raising=True):
        os.kill(int(pidfile.read()), signal.SIGTERM)

    assert not text_file.exists()


def test_temporary_files_failed_cleanup(caplog, qtbot, tmpdir, py_proc,
                                        runner):
    """Delete a temporary file from the script so cleanup fails."""
    test_file = tmpdir / 'test'
    test_file.write('foo')

    cmd, args = py_proc(r"""
        import os
        os.remove(os.environ['QUTE_HTML'])
    """)

    with caplog.at_level(logging.ERROR):
        with qtbot.waitSignal(runner.finished, raising=True, timeout=10000):
            runner.run(cmd, *args, env={'QUTE_HTML': str(test_file)})

    assert len(caplog.records) == 1
    expected = ("Failed to delete tempfile {file} ([Errno 2] No such file or "
                "directory: '{file}')!".format(file=test_file))
    assert caplog.records[0].message == expected


def test_dummy_runner(qtbot):
    runner = userscripts._DummyUserscriptRunner(0)
    with pytest.raises(cmdexc.CommandError):
        with qtbot.waitSignal(runner.finished):
            runner.run('cmd', 'arg')


def test_store_source_none():
    assert userscripts.store_source(None) == {}


def test_store_source(stubs):
    expected_text = 'This is text'
    expected_html = 'This is HTML'

    frame = stubs.FakeWebFrame(plaintext=expected_text, html=expected_html)
    env = userscripts.store_source(frame)

    with open(env['QUTE_TEXT'], 'r', encoding='utf-8') as f:
        text = f.read()
    with open(env['QUTE_HTML'], 'r', encoding='utf-8') as f:
        html = f.read()

    os.remove(env['QUTE_TEXT'])
    os.remove(env['QUTE_HTML'])

    assert set(env.keys()) == {'QUTE_TEXT', 'QUTE_HTML'}
    assert text == expected_text
    assert html == expected_html
    assert env['QUTE_TEXT'].endswith('.txt')
    assert env['QUTE_HTML'].endswith('.html')
