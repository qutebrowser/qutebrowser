# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from qutebrowser.commands import userscripts
from qutebrowser.utils import utils


@pytest.mark.posix
class TestQtFIFOReader:

    @pytest.fixture
    def reader(self, tmpdir, qapp):
        fifo_path = str(tmpdir / 'fifo')
        os.mkfifo(fifo_path)  # pylint: disable=no-member,useless-suppression
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
def runner(request, runtime_tmpdir):
    if (not utils.is_posix and
            request.param is userscripts._POSIXUserscriptRunner):
        pytest.skip("Requires a POSIX os")
        raise utils.Unreachable
    return request.param()


def test_command(qtbot, py_proc, runner):
    cmd, args = py_proc(r"""
        import os
        with open(os.environ['QUTE_FIFO'], 'w') as f:
            f.write('foo\n')
    """)
    with qtbot.waitSignal(runner.finished, timeout=10000):
        with qtbot.waitSignal(runner.got_cmd, timeout=10000) as blocker:
            runner.prepare_run(cmd, *args)
            runner.store_html('')
            runner.store_text('')
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

    with qtbot.waitSignal(runner.finished, timeout=10000):
        with qtbot.waitSignal(runner.got_cmd, timeout=10000) as blocker:
            runner.prepare_run(cmd, *args, env=env)
            runner.store_html('')
            runner.store_text('')

    data = blocker.args[0]
    ret_env = json.loads(data)
    assert 'QUTEBROWSER_TEST_1' in ret_env
    assert 'QUTEBROWSER_TEST_2' in ret_env


def test_source(qtbot, py_proc, runner):
    """Make sure the page source is read and cleaned up correctly."""
    cmd, args = py_proc(r"""
        import os
        import json

        data = {
            'html_file': os.environ['QUTE_HTML'],
            'text_file': os.environ['QUTE_TEXT'],
        }

        with open(os.environ['QUTE_HTML'], 'r') as f:
            data['html'] = f.read()

        with open(os.environ['QUTE_TEXT'], 'r') as f:
            data['text'] = f.read()

        with open(os.environ['QUTE_FIFO'], 'w') as f:
            json.dump(data, f)
            f.write('\n')
    """)

    with qtbot.waitSignal(runner.finished, timeout=10000):
        with qtbot.waitSignal(runner.got_cmd, timeout=10000) as blocker:
            runner.prepare_run(cmd, *args)
            runner.store_html('This is HTML')
            runner.store_text('This is text')

    data = blocker.args[0]
    parsed = json.loads(data)
    assert parsed['text'] == 'This is text'
    assert parsed['html'] == 'This is HTML'

    assert not os.path.exists(parsed['text_file'])
    assert not os.path.exists(parsed['html_file'])


def test_command_with_error(qtbot, py_proc, runner, caplog):
    cmd, args = py_proc(r"""
        import sys, os, json

        with open(os.environ['QUTE_FIFO'], 'w') as f:
            json.dump(os.environ['QUTE_TEXT'], f)
            f.write('\n')

        sys.exit(1)
    """)

    with caplog.at_level(logging.ERROR):
        with qtbot.waitSignal(runner.finished, timeout=10000):
            with qtbot.waitSignal(runner.got_cmd, timeout=10000) as blocker:
                runner.prepare_run(cmd, *args)
                runner.store_text('Hello World')
                runner.store_html('')

    data = json.loads(blocker.args[0])
    assert not os.path.exists(data)


def test_killed_command(qtbot, tmpdir, py_proc, runner, caplog):
    data_file = tmpdir / 'data'
    watcher = QFileSystemWatcher()
    watcher.addPath(str(tmpdir))

    cmd, args = py_proc(r"""
        import os
        import time
        import sys
        import json

        data = {
            'pid': os.getpid(),
            'text_file': os.environ['QUTE_TEXT'],
        }

        # We can't use QUTE_FIFO to transmit the PID because that wouldn't work
        # on Windows, where QUTE_FIFO is only monitored after the script has
        # exited.

        with open(sys.argv[1], 'w') as f:
            json.dump(data, f)

        time.sleep(30)
    """)
    args.append(str(data_file))

    with qtbot.waitSignal(watcher.directoryChanged, timeout=10000):
        runner.prepare_run(cmd, *args)
        runner.store_text('Hello World')
        runner.store_html('')

    # Make sure the PID was written to the file, not just the file created
    time.sleep(0.5)

    data = json.load(data_file)

    with caplog.at_level(logging.ERROR):
        with qtbot.waitSignal(runner.finished):
            os.kill(int(data['pid']), signal.SIGTERM)

    assert not os.path.exists(data['text_file'])


def test_temporary_files_failed_cleanup(caplog, qtbot, py_proc, runner):
    """Delete a temporary file from the script so cleanup fails."""
    cmd, args = py_proc(r"""
        import os
        os.remove(os.environ['QUTE_HTML'])
    """)

    with caplog.at_level(logging.ERROR):
        with qtbot.waitSignal(runner.finished, timeout=10000):
            runner.prepare_run(cmd, *args)
            runner.store_text('')
            runner.store_html('')

    assert len(caplog.records) == 1
    expected = "Failed to delete tempfile"
    assert caplog.messages[0].startswith(expected)


def test_unicode_error(caplog, qtbot, py_proc, runner):
    cmd, args = py_proc(r"""
        import os
        with open(os.environ['QUTE_FIFO'], 'wb') as f:
            f.write(b'\x80')
    """)
    with caplog.at_level(logging.ERROR):
        with qtbot.waitSignal(runner.finished, timeout=10000):
            runner.prepare_run(cmd, *args)
            runner.store_text('')
            runner.store_html('')

    assert len(caplog.records) == 1
    expected = "Invalid unicode in userscript output: "
    assert caplog.messages[0].startswith(expected)


@pytest.mark.fake_os('unknown')
def test_unsupported(tabbed_browser_stubs):
    with pytest.raises(userscripts.UnsupportedError, match="Userscripts are "
                       "not supported on this platform!"):
        userscripts.run_async(tab=None, cmd=None, win_id=0, env=None)
