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
import socket
import collections

import pytest
from PyQt5.QtCore import pyqtSignal

from tests.integration import testprocess  # pylint: disable=import-error


Request = collections.namedtuple('Request', 'verb, url')


class InvalidLine(Exception):

    """Exception raised when HTTPBin prints a line which is not parsable."""

    pass


class HTTPBin(testprocess.Process):

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

    PROCESS_NAME = 'webserver_sub'

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
        return self._get_data()

    def _parse_line(self, line):
        if line == (' * Running on http://127.0.0.1:{}/ (Press CTRL+C to '
                    'quit)'.format(self.port)):
            self.ready.emit()
            return None

        match = self.LOG_RE.match(line)
        if match is None:
            raise InvalidLine
        # FIXME do we need to allow other options?
        assert match.group('protocol') == 'HTTP/1.1'

        return Request(verb=match.group('verb'), url=match.group('url'))

    def _executable_args(self):
        return [str(self.port)]

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
def httpbin_clean(httpbin):
    """Fixture to clean httpbin request list after each test."""
    yield
    httpbin.after_test()
