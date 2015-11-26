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
import json
import socket
import os.path

import pytest
from PyQt5.QtCore import pyqtSignal

import testprocess  # pylint: disable=import-error


class Request(testprocess.Line):

    """A parsed line from the httpbin/flask log output.

    Attributes:
        verb/path/status: Parsed from the log output.
    """

    def __init__(self, data):
        super().__init__(data)
        try:
            parsed = json.loads(data)
        except ValueError:
            raise testprocess.InvalidLine(data)

        assert isinstance(parsed, dict)
        assert set(parsed.keys()) == {'path', 'verb', 'status'}

        self.verb = parsed['verb']

        path = parsed['path']
        self.path = '/' if path == '/' else path.rstrip('/')

        self.status = parsed['status']

        missing_paths = ['/favicon.ico', '/does-not-exist']

        if self.path in missing_paths:
            assert self.status == 404
        else:
            assert self.status < 400

    def __eq__(self, other):
        return NotImplemented


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

    def __hash__(self):
        return hash(('ExpectedRequest', self.verb, self.path))

    def __repr__(self):
        return ('ExpectedRequest(verb={!r}, path={!r})'
                .format(self.verb, self.path))


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
