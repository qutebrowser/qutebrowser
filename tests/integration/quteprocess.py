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

import pytest
from PyQt5.QtCore import pyqtSignal

import testprocess  # pylint: disable=import-error
from qutebrowser.misc import ipc


class NoLineMatch(Exception):

    """Raised by LogLine on unmatched lines."""

    pass


class LogLine:

    LOG_RE = re.compile(r"""
        (?P<timestamp>\d\d:\d\d:\d\d)
        \ (?P<loglevel>VDEBUG|DEBUG|INFO|WARNING|ERROR)
        \ +(?P<category>\w+)
        \ +(?P<module>(\w+|Unknown\ module)):(?P<function>\w+):(?P<line>\d+)
        \ (?P<message>.+)
    """, re.VERBOSE)

    def __init__(self, line):
        match = self.LOG_RE.match(line)
        if match is None:
            raise NoLineMatch(line)
        self.__dict__.update(match.groupdict())
        self.expected = False


class QuteProc(testprocess.Process):

    """A running qutebrowser process used for tests.

    Attributes:
        _ipc_socket: The IPC socket of the started instance.
        _httpbin: The HTTPBin webserver.
    """

    executing_command = pyqtSignal()
    setting_done = pyqtSignal()
    url_loaded = pyqtSignal()
    got_error = pyqtSignal()

    def __init__(self, httpbin, parent=None):
        super().__init__(parent)
        self._httpbin = httpbin
        self._ipc_socket = None

    def _parse_line(self, line):
        try:
            log_line = LogLine(line)
        except NoLineMatch:
            if line.startswith('  '):
                # Multiple lines in some log output...
                return None
            elif not line.strip():
                return None
            else:
                raise testprocess.InvalidLine

        if (log_line.loglevel in ['INFO', 'WARNING', 'ERROR'] or
                pytest.config.getoption('--verbose')):
            print(line)

        start_okay_message = ("load status for "
                              "<qutebrowser.browser.webview.WebView tab_id=0 "
                              "url='about:blank'>: LoadStatus.success")

        url_loaded_pattern = re.compile(
            r"load status for <qutebrowser.browser.webview.WebView tab_id=\d+ "
            r"url='[^']+'>: LoadStatus.success")

        if (log_line.category == 'ipc' and
                log_line.message.startswith("Listening as ")):
            self._ipc_socket = log_line.message.split(' ', maxsplit=2)[2]
        elif (log_line.category == 'webview' and
                log_line.message == start_okay_message):
            self.ready.emit()
        elif (log_line.category == 'commands' and
              log_line.module == 'command' and log_line.function == 'run' and
              log_line.message.startswith('Calling ')):
            self.executing_command.emit()
        elif (log_line.category == 'config' and log_line.message.startswith(
                'Config option changed: ')):
            self.setting_done.emit()
        elif (log_line.category == 'webview' and
                url_loaded_pattern.match(log_line.message)):
            self.url_loaded.emit()
        elif log_line.loglevel in ['WARNING', 'ERROR']:
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

    def after_test(self):
        bad_msgs = [msg for msg in self._data
                    if msg.loglevel not in ['VDEBUG', 'DEBUG', 'INFO']
                    and not msg.expected]
        super().after_test()
        if bad_msgs:
            text = 'Logged unexpected errors:\n\n' + '\n'.join(
                str(e) for e in bad_msgs)
            pytest.fail(text, pytrace=False)

    def send_cmd(self, command):
        assert self._ipc_socket is not None
        with self._wait_signal(self.executing_command):
            ipc.send_to_running_instance(self._ipc_socket, [command],
                                         target_arg='')
        # Wait a bit in cause the command triggers any error.
        time.sleep(0.5)

    def set_setting(self, sect, opt, value):
        with self._wait_signal(self.setting_done):
            self.send_cmd(':set "{}" "{}" "{}"'.format(sect, opt, value))

    def open_path(self, path, new_tab=False):
        url = 'http://localhost:{}/{}'.format(self._httpbin.port, path)
        with self._wait_signal(self.url_loaded):
            if new_tab:
                self.send_cmd(':open -t ' + url)
            else:
                self.send_cmd(':open ' + url)

    def mark_expected(self, category=None, loglevel=None, msg=None):
        """Mark a given logging message as expected."""
        for item in self._data:
            if category is not None and item.category != category:
                continue
            elif loglevel is not None and item.loglevel != loglevel:
                continue
            elif msg is not None and item.message != msg:
                continue
            item.expected = True


@pytest.yield_fixture
def quteproc(qapp, httpbin):
    """Fixture for qutebrowser process."""
    proc = QuteProc(httpbin)
    proc.start()
    yield proc
    proc.terminate()
    proc.after_test()
