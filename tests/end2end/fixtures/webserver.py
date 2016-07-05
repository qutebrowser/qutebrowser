# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import json
import socket
import os.path
import http.client

import pytest
from PyQt5.QtCore import pyqtSignal, QUrl

from end2end.fixtures import testprocess


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
        self._check_status()

    def _check_status(self):
        """Check if the http status is what we expected."""
        # WORKAROUND for https://github.com/PyCQA/pylint/issues/399 (?)
        # pylint: disable=no-member, useless-suppression
        path_to_statuses = {
            '/favicon.ico': [http.client.NOT_FOUND],
            '/does-not-exist': [http.client.NOT_FOUND],
            '/custom/redirect-later': [http.client.FOUND],
            '/basic-auth/user/password':
                [http.client.UNAUTHORIZED, http.client.OK],
            '/redirect-to': [http.client.FOUND],
            '/status/404': [http.client.NOT_FOUND],
            '/cookies/set': [http.client.FOUND],
        }

        sanitized = QUrl('http://localhost' + self.path).path()  # Remove ?foo
        expected_statuses = path_to_statuses.get(sanitized, [http.client.OK])
        assert self.status in expected_statuses

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
            return self.verb == other.verb and self.path == other.path
        else:
            return NotImplemented

    def __hash__(self):
        return hash(('ExpectedRequest', self.verb, self.path))

    def __repr__(self):
        return ('ExpectedRequest(verb={!r}, path={!r})'
                .format(self.verb, self.path))


class WebserverProcess(testprocess.Process):

    """Abstraction over a running HTTPbin server process.

    Reads the log from its stdout and parses it.

    Signals:
        new_request: Emitted when there's a new request received.
    """

    new_request = pyqtSignal(Request)
    Request = Request  # So it can be used from the fixture easily.
    ExpectedRequest = ExpectedRequest

    KEYS = ['verb', 'path']

    def __init__(self, script, parent=None):
        super().__init__(parent)
        self._script = script
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
        self._log(line)
        started_re = re.compile(r' \* Running on https?://127\.0\.0\.1:{}/ '
                                r'\(Press CTRL\+C to quit\)'.format(self.port))
        if started_re.fullmatch(line):
            self.ready.emit()
            return None
        return Request(line)

    def _executable_args(self):
        if hasattr(sys, 'frozen'):
            executable = os.path.join(os.path.dirname(sys.executable),
                                      self._script)
            args = []
        else:
            executable = sys.executable
            py_file = os.path.join(os.path.dirname(__file__),
                                   self._script + '.py')
            args = [py_file]
        return executable, args

    def _default_args(self):
        return [str(self.port)]

    def cleanup(self):
        """Clean up and shut down the process."""
        self.proc.terminate()
        self.proc.waitForFinished()


@pytest.yield_fixture(scope='session', autouse=True)
def httpbin(qapp):
    """Fixture for an httpbin object which ensures clean setup/teardown."""
    httpbin = WebserverProcess('webserver_sub')
    httpbin.start()
    yield httpbin
    httpbin.cleanup()


@pytest.yield_fixture(autouse=True)
def httpbin_after_test(httpbin, request):
    """Fixture to clean httpbin request list after each test."""
    request.node._httpbin_log = httpbin.captured_log
    yield
    httpbin.after_test()


@pytest.yield_fixture
def ssl_server(request, qapp):
    """Fixture for a webserver with a self-signed SSL certificate.

    This needs to be explicitly used in a test, and overwrites the httpbin log
    used in that test.
    """
    server = WebserverProcess('webserver_sub_ssl')
    request.node._httpbin_log = server.captured_log
    server.start()
    yield server
    server.after_test()
    server.cleanup()
