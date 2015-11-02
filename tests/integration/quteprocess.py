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

import pytest
from PyQt5.QtCore import pyqtSignal

import testprocess  # pylint: disable=import-error
from qutebrowser.misc import ipc
from qutebrowser.utils import log


class NoLineMatch(Exception):

    """Raised by LogLine on unmatched lines."""

    pass


class LogLine:

    """A parsed line from the qutebrowser log output.

    Attributes:
        timestamp/loglevel/category/module/function/line/message:
            Parsed from the log output.
        _line: The entire unparsed line.
        expected: Whether the message was expected or not.
    """

    LOG_RE = re.compile(r"""
        (?P<timestamp>\d\d:\d\d:\d\d)
        \ (?P<loglevel>VDEBUG|DEBUG|INFO|WARNING|ERROR)
        \ +(?P<category>\w+)
        \ +(?P<module>(\w+|Unknown\ module)):(?P<function>\w+):(?P<line>\d+)
        \ (?P<message>.+)
    """, re.VERBOSE)

    def __init__(self, line):
        self._line = line
        match = self.LOG_RE.match(line)
        if match is None:
            raise NoLineMatch(line)
        self.__dict__.update(match.groupdict())

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

        self.function = match.group('function')
        self.line = int(match.group('line'))
        self.message = match.group('message')

        self.expected = self._is_ignored()

    def __repr__(self):
        return 'LogLine({!r})'.format(self._line)

    def _is_ignored(self):
        """Check if the message is listed in qt_log_ignore."""
        regexes = pytest.config.getini('qt_log_ignore')
        for regex in regexes:
            if re.match(regex, self.message):
                return True
        return False


class QuteProc(testprocess.Process):

    """A running qutebrowser process used for tests.

    Attributes:
        _ipc_socket: The IPC socket of the started instance.
        _httpbin: The HTTPBin webserver.
    """

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
            elif (line == "QWaitCondition: Destroyed while threads are still "
                          "waiting"):
                # Happens on Windows during exit sometimes
                return None
            else:
                raise testprocess.InvalidLine

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

    def after_test(self):
        bad_msgs = [msg for msg in self._data
                    if msg.loglevel > logging.INFO and not msg.expected]
        super().after_test()
        if bad_msgs:
            text = 'Logged unexpected errors:\n\n' + '\n'.join(
                str(e) for e in bad_msgs)
            pytest.fail(text, pytrace=False)

    def send_cmd(self, command):
        assert self._ipc_socket is not None

        ipc.send_to_running_instance(self._ipc_socket, [command],
                                     target_arg='')
        self.wait_for(category='commands', module='command', function='run',
                      message='Calling *')
        # Wait a bit in cause the command triggers any error.
        time.sleep(0.5)

    def set_setting(self, sect, opt, value):
        self.send_cmd(':set "{}" "{}" "{}"'.format(sect, opt, value))
        self.wait_for(category='config', message='Config option changed: *')

    def open_path(self, path, new_tab=False):
        url_loaded_pattern = re.compile(
            r"load status for <qutebrowser.browser.webview.WebView tab_id=\d+ "
            r"url='[^']+'>: LoadStatus.success")

        url = 'http://localhost:{}/{}'.format(self._httpbin.port, path)
        if new_tab:
            self.send_cmd(':open -t ' + url)
        else:
            self.send_cmd(':open ' + url)
        self.wait_for(category='webview', message=url_loaded_pattern)

    def mark_expected(self, category=None, loglevel=None, message=None):
        """Mark a given logging message as expected."""
        found_message = False

        # Search existing messages
        for item in self._data:
            if category is not None and item.category != category:
                continue
            elif loglevel is not None and item.loglevel != loglevel:
                continue
            elif message is not None and item.message != message:
                continue
            item.expected = True
            found_message = True

        # If there is none, wait for the message
        if not found_message:
            line = self.wait_for(category=category, loglevel=loglevel,
                                 message=message)
            line.expected = True


@pytest.yield_fixture
def quteproc(qapp, httpbin):
    """Fixture for qutebrowser process."""
    proc = QuteProc(httpbin)
    proc.start()
    yield proc
    proc.terminate()
    proc.after_test()
