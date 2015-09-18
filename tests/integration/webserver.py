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

"""Fixtures for the httpbin webserver."""

import re
import sys
import socket
import os.path
import collections

import pytest
import pytestqt.plugin  # pylint: disable=import-error
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QProcess, QObject


Request = collections.namedtuple('Request', 'verb, url')


class InvalidLine(Exception):

    """Exception raised when HTTPBin prints a line which is not parsable."""

    pass


class HTTPBin(QObject):

    """Abstraction over a running HTTPbin server process.

    Reads the log from its stdout and parses it.

    Class attributes:
        LOG_RE: Used to parse the CLF log which httpbin outputs.

    Signals:
        ready: Emitted when the server finished starting up.
        new_request: Emitted when there's a new request received.
    """

    ready = pyqtSignal()
    new_request = pyqtSignal(Request)

    LOG_RE = re.compile(r"""
        (?P<host>[^ ]*)
        \ ([^ ]*) # ignored
        \ (?P<user>[^ ]*)
        \ \[(?P<date>[^]]*)\]
        \ "(?P<request>
            (?P<verb>[^ ]*)
            \ (?P<url>[^ ]*)
            \ (?P<protocol>[^ ]*)
        )"
        \ (?P<status>[^ ]*)
        \ (?P<size>[^ ]*)
    """, re.VERBOSE)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._invalid = False
        self._requests = []
        self.port = self._get_port()
        self.proc = QProcess()
        self.proc.setReadChannel(QProcess.StandardError)

    def _get_port(self):
        """Get a random free port to use for the server."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def get_requests(self):
        """Get the requests to the server during this test.

        Also waits for 0.5s to make sure any new requests are received.
        """
        self.proc.waitForReadyRead(500)
        self.read_log()
        return self._requests

    @pyqtSlot()
    def read_log(self):
        """Read the log from httpbin's stdout and parse it."""
        while self.proc.canReadLine():
            line = self.proc.readLine()
            line = bytes(line).decode('utf-8').rstrip('\r\n')
            print(line)

            if line == (' * Running on http://127.0.0.1:{}/ (Press CTRL+C to '
                        'quit)'.format(self.port)):
                self.ready.emit()
                continue

            match = self.LOG_RE.match(line)
            if match is None:
                self._invalid = True
                print("INVALID: {}".format(line))
                continue

            # FIXME do we need to allow other options?
            assert match.group('protocol') == 'HTTP/1.1'

            request = Request(verb=match.group('verb'), url=match.group('url'))
            print(request)
            self._requests.append(request)
            self.new_request.emit(request)

    def start(self):
        """Start the webserver."""
        if hasattr(sys, 'frozen'):
            executable = os.path.join(os.path.dirname(sys.executable),
                                      'webserver_sub')
            args = []
        else:
            executable = sys.executable
            args = [os.path.join(os.path.dirname(__file__),
                                 'webserver_sub.py')]

        self.proc.start(executable, args + [str(self.port)])
        ok = self.proc.waitForStarted()
        assert ok
        self.proc.readyRead.connect(self.read_log)

    def after_test(self):
        """Clean request list after each test.

        Also checks self._invalid so the test counts as failed if there were
        unexpected output lines earlier.
        """
        self._requests.clear()
        if self._invalid:
            raise InvalidLine

    def cleanup(self):
        """Clean up and shut down the process."""
        self.proc.terminate()
        self.proc.waitForFinished()


@pytest.yield_fixture(scope='session', autouse=True)
def httpbin(qapp):
    """Fixture for a httpbin object which ensures clean setup/teardown."""
    httpbin = HTTPBin()

    blocker = pytestqt.plugin.SignalBlocker(timeout=5000, raising=True)
    blocker.connect(httpbin.ready)
    with blocker:
        httpbin.start()

    yield httpbin

    httpbin.cleanup()


@pytest.yield_fixture(autouse=True)
def httpbin_clean(httpbin):
    """Fixture to clean httpbin request list after each test."""
    yield
    httpbin.after_test()
