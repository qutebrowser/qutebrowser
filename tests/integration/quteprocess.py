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

# pylint doesn't understand the testprocess import
# pylint: disable=no-member

"""Fixtures to run qutebrowser in a QProcess and communicate."""

import re
import sys
import time
import os.path
import datetime
import logging
import tempfile

import yaml
import pytest
from PyQt5.QtCore import pyqtSignal, QUrl

import testprocess  # pylint: disable=import-error
from qutebrowser.misc import ipc
from qutebrowser.utils import log, utils


def is_ignored_qt_message(message):
    """Check if the message is listed in qt_log_ignore."""
    regexes = pytest.config.getini('qt_log_ignore')
    for regex in regexes:
        if re.match(regex, message):
            return True
    return False


class LogLine(testprocess.Line):

    """A parsed line from the qutebrowser log output.

    Attributes:
        timestamp/loglevel/category/module/function/line/message:
            Parsed from the log output.
        expected: Whether the message was expected or not.
    """

    LOG_RE = re.compile(r"""
        (?P<timestamp>\d\d:\d\d:\d\d)
        \ (?P<loglevel>VDEBUG|DEBUG|INFO|WARNING|ERROR)
        \ +(?P<category>\w+)
        \ +(?P<module>(\w+|Unknown\ module)):
           (?P<function>[^"][^:]*|"[^"]+"):
           (?P<line>\d+)
        \ (?P<message>.+)
    """, re.VERBOSE)

    def __init__(self, data):
        super().__init__(data)
        match = self.LOG_RE.match(data)
        if match is None:
            raise testprocess.InvalidLine(data)

        self.timestamp = datetime.datetime.strptime(match.group('timestamp'),
                                                    '%H:%M:%S')
        loglevel = match.group('loglevel')
        if loglevel == 'VDEBUG':
            self.loglevel = log.VDEBUG_LEVEL
        else:
            self.loglevel = getattr(logging, loglevel)

        self.category = match.group('category')

        module = match.group('module')
        if module == 'Unknown module':
            self.module = None
        else:
            self.module = module

        function = match.group('function')
        if function == 'none':
            self.function = None
        else:
            self.function = function.strip('"')

        line = int(match.group('line'))
        if self.function is None and line == 0:
            self.line = None
        else:
            self.line = line

        msg_match = re.match(r'^(\[(?P<prefix>\d+s ago)\] )?(?P<message>.*)',
                             match.group('message'))
        self.prefix = msg_match.group('prefix')
        self.message = msg_match.group('message')

        self.expected = is_ignored_qt_message(self.message)


class QuteProc(testprocess.Process):

    """A running qutebrowser process used for tests.

    Attributes:
        _delay: Delay to wait between commands.
        _ipc_socket: The IPC socket of the started instance.
        _httpbin: The HTTPBin webserver.
    """

    got_error = pyqtSignal()

    KEYS = ['timestamp', 'loglevel', 'category', 'module', 'function', 'line',
            'message']

    def __init__(self, httpbin, delay, parent=None):
        super().__init__(parent)
        self._delay = delay
        self._httpbin = httpbin
        self._ipc_socket = None

    def _parse_line(self, line):
        try:
            log_line = LogLine(line)
        except testprocess.InvalidLine:
            if line.startswith('  '):
                # Multiple lines in some log output...
                return None
            elif not line.strip():
                return None
            elif is_ignored_qt_message(line):
                return None
            else:
                raise

        if (log_line.loglevel in ['INFO', 'WARNING', 'ERROR'] or
                pytest.config.getoption('--verbose')):
            print(line)

        start_okay_message = ("load status for "
                              "<qutebrowser.browser.webview.WebView tab_id=0 "
                              "url='about:blank'>: LoadStatus.success")

        if (log_line.category == 'ipc' and
                log_line.message.startswith("Listening as ")):
            self._ipc_socket = log_line.message.split(' ', maxsplit=2)[2]
        elif (log_line.category == 'webview' and
                log_line.message == start_okay_message):
            self.ready.emit()
        elif log_line.loglevel > logging.INFO:
            self.got_error.emit()

        return log_line

    def _executable_args(self):
        if hasattr(sys, 'frozen'):
            executable = os.path.join(os.path.dirname(sys.executable),
                                      'qutebrowser')
            args = []
        else:
            executable = sys.executable
            args = ['-m', 'qutebrowser']
        args += ['--debug', '--no-err-windows', '--temp-basedir',
                 'about:blank']
        return executable, args

    def _path_to_url(self, path):
        if path.startswith('about:') or path.startswith('qute:'):
            return path
        else:
            return 'http://localhost:{}/{}'.format(self._httpbin.port, path)

    def after_test(self):
        bad_msgs = [msg for msg in self._data
                    if msg.loglevel > logging.INFO and not msg.expected]
        super().after_test()
        if bad_msgs:
            text = 'Logged unexpected errors:\n\n' + '\n'.join(
                str(e) for e in bad_msgs)
            pytest.fail(text, pytrace=False)

    def send_cmd(self, command, count=None):
        assert self._ipc_socket is not None

        time.sleep(self._delay / 1000)

        if count is not None:
            command = ':{}:{}'.format(count, command.lstrip(':'))

        ipc.send_to_running_instance(self._ipc_socket, [command],
                                     target_arg='')
        self.wait_for(category='commands', module='command', function='run',
                      message='command called: *')

    def set_setting(self, sect, opt, value):
        self.send_cmd(':set "{}" "{}" "{}"'.format(sect, opt, value))
        self.wait_for(category='config', message='Config option changed: *')

    def open_path(self, path, new_tab=False):
        url = self._path_to_url(path)
        if new_tab:
            self.send_cmd(':open -t ' + url)
        else:
            self.send_cmd(':open ' + url)
        self.wait_for_load_finished(path)

    def mark_expected(self, category=None, loglevel=None, message=None):
        """Mark a given logging message as expected."""
        line = self.wait_for(category=category, loglevel=loglevel,
                             message=message)
        line.expected = True

    def wait_for_load_finished(self, path, timeout=15000):
        """Wait until any tab has finished loading."""
        url = self._path_to_url(path)
        # We really need the same representation that the webview uses in its
        # __repr__
        url = utils.elide(QUrl(url).toDisplayString(QUrl.EncodeUnicode), 100)
        pattern = re.compile(
            r"(load status for <qutebrowser.browser.webview.WebView "
            r"tab_id=\d+ url='{url}'>: LoadStatus.success|fetch: "
            r"PyQt5.QtCore.QUrl\('{url}'\) -> .*)".format(url=re.escape(url)))
        self.wait_for(message=pattern, timeout=timeout)

    def get_session(self):
        """Save the session and get the parsed session data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session = os.path.join(tmpdir, 'session.yml')
            self.send_cmd(':session-save "{}"'.format(session))
            self.wait_for(category='message', loglevel=logging.INFO,
                          message='Saved session {}.'.format(session))
            with open(session, encoding='utf-8') as f:
                data = f.read()

        print(data)
        return yaml.load(data)


@pytest.yield_fixture(scope='module')
def quteproc(qapp, httpbin, request):
    """Fixture for qutebrowser process."""
    delay = request.config.getoption('--qute-delay')
    proc = QuteProc(httpbin, delay)
    proc.start()
    yield proc
    proc.terminate()


@pytest.yield_fixture(autouse=True)
def quteproc_after_test(quteproc):
    """Fixture to run cleanup tasks after each test."""
    quteproc.before_test()
    yield
    quteproc.after_test()
