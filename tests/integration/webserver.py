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

"""Fixtures for the httpbin webserver."""

import re
import sys
import socket
import os.path
import functools

import pytest
from PyQt5.QtCore import pyqtSignal

import testprocess  # pylint: disable=import-error


class Request(testprocess.Line):

    """A parsed line from the httpbin/flask log output.

    Attributes:
        timestamp/verb/path/status: Parsed from the log output.

    Class attributes:
        LOG_RE: Used to parse the CLF log which httpbin outputs.
    """

    LOG_RE = re.compile(r"""
        (?P<host>[^ ]*)
        \ ([^ ]*) # ignored
        \ (?P<user>[^ ]*)
        \ \[(?P<date>[^]]*)\]
        \ "(?P<request>
            (?P<verb>[^ ]*)
            \ (?P<path>[^ ]*)
            \ (?P<protocol>[^ ]*)
        )"
        \ (?P<status>[^ ]*)
        \ (?P<size>[^ ]*)
    """, re.VERBOSE)

    def __init__(self, data):
        super().__init__(data)
        match = self.LOG_RE.match(data)
        if match is None:
            raise testprocess.InvalidLine(data)

        assert match.group('host') == '127.0.0.1'
        assert match.group('user') == '-'
        self.timestamp = match.group('date')
        self.verb = match.group('verb')

        # FIXME do we need to allow other options?
        assert match.group('protocol') == 'HTTP/1.1'
        assert self.verb == 'GET'

        self.path = match.group('path')
        self.status = int(match.group('status'))

        missing_paths = ['/favicon.ico', '/does-not-exist']

        if self.path in missing_paths:
            assert self.status == 404
        else:
            assert self.status < 400

        assert match.group('size') == '-'

    def __eq__(self, other):
        return NotImplemented


@functools.total_ordering
class ExpectedRequest:

    """Class to compare expected requests easily."""

    def __init__(self, verb, path):
        self.verb = verb
        self.path = path

    @classmethod
    def from_request(cls, request):
        """Create an ExpectedRequest from a Request."""
        return cls(request.verb, request.path)

    def __eq__(self, other):
        if isinstance(other, (Request, ExpectedRequest)):
            return (self.verb == other.verb and
                    self.path == other.path)
        else:
            return NotImplemented

    def __lt__(self, other):
        if isinstance(other, (Request, ExpectedRequest)):
            return (self.verb, self.path) < (other.verb, other.path)
        else:
            return NotImplemented

    def __str__(self):
        return '<ExpectedRequest {} "{}">'.format(self.verb, self.path)

    __repr__ = __str__


class HTTPBin(testprocess.Process):

    """Abstraction over a running HTTPbin server process.

    Reads the log from its stdout and parses it.

    Signals:
        new_request: Emitted when there's a new request received.
    """

    new_request = pyqtSignal(Request)
    Request = Request  # So it can be used from the fixture easily.
    ExpectedRequest = ExpectedRequest

    KEYS = ['verb', 'path']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.port = self._get_port()
        self.new_data.connect(self.new_request)

    def _get_port(self):
        """Get a random free port to use for the server."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def get_requests(self):
        """Get the requests to the server during this test."""
        requests = self._get_data()
        return [r for r in requests if r.path != '/favicon.ico']

    def _parse_line(self, line):
        print(line)
        if line == (' * Running on http://127.0.0.1:{}/ (Press CTRL+C to '
                    'quit)'.format(self.port)):
            self.ready.emit()
            return None
        return Request(line)

    def _executable_args(self):
        if hasattr(sys, 'frozen'):
            executable = os.path.join(os.path.dirname(sys.executable),
                                      'webserver_sub')
            args = [str(self.port)]
        else:
            executable = sys.executable
            py_file = os.path.join(os.path.dirname(__file__),
                                   'webserver_sub.py')
            args = [py_file, str(self.port)]
        return executable, args

    def cleanup(self):
        """Clean up and shut down the process."""
        self.proc.terminate()
        self.proc.waitForFinished()


@pytest.yield_fixture(scope='session', autouse=True)
def httpbin(qapp):
    """Fixture for a httpbin object which ensures clean setup/teardown."""
    httpbin = HTTPBin()
    httpbin.start()
    yield httpbin
    httpbin.cleanup()


@pytest.yield_fixture(autouse=True)
def httpbin_after_test(httpbin):
    """Fixture to clean httpbin request list after each test."""
    yield
    httpbin.after_test()
