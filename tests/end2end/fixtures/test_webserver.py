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

"""Test the server webserver used for tests."""

import json
import urllib.request
import urllib.error
from http import HTTPStatus

import pytest


@pytest.mark.parametrize('path, content, expected', [
    ('/', 'qutebrowser test webserver', True),
    # https://github.com/Runscope/server/issues/245
    ('/', 'www.google-analytics.com', False),
    ('/data/hello.txt', 'Hello World!', True),
])
def test_server(server, qtbot, path, content, expected):
    with qtbot.waitSignal(server.new_request, timeout=100):
        url = 'http://localhost:{}{}'.format(server.port, path)
        try:
            response = urllib.request.urlopen(url)
        except urllib.error.HTTPError as e:
            # "Though being an exception (a subclass of URLError), an HTTPError
            # can also function as a non-exceptional file-like return value
            # (the same thing that urlopen() returns)."
            # ...wat
            print(e.read().decode('utf-8'))
            raise

    data = response.read().decode('utf-8')

    assert server.get_requests() == [server.ExpectedRequest('GET', path)]
    assert (content in data) == expected


@pytest.mark.parametrize('line, verb, path, equal', [
    ({'verb': 'GET', 'path': '/', 'status': HTTPStatus.OK}, 'GET', '/', True),
    ({'verb': 'GET', 'path': '/foo/', 'status': HTTPStatus.OK},
     'GET', '/foo', True),
    ({'verb': 'GET', 'path': '/relative-redirect', 'status': HTTPStatus.FOUND},
     'GET', '/relative-redirect', True),
    ({'verb': 'GET', 'path': '/absolute-redirect', 'status': HTTPStatus.FOUND},
     'GET', '/absolute-redirect', True),
    ({'verb': 'GET', 'path': '/redirect-to', 'status': HTTPStatus.FOUND},
     'GET', '/redirect-to', True),
    ({'verb': 'GET', 'path': '/redirect-self', 'status': HTTPStatus.FOUND},
     'GET', '/redirect-self', True),
    ({'verb': 'GET', 'path': '/content-size', 'status': HTTPStatus.OK},
     'GET', '/content-size', True),
    ({'verb': 'GET', 'path': '/twenty-mb', 'status': HTTPStatus.OK},
     'GET', '/twenty-mb', True),
    ({'verb': 'GET', 'path': '/500-inline',
      'status': HTTPStatus.INTERNAL_SERVER_ERROR}, 'GET', '/500-inline', True),
    ({'verb': 'GET', 'path': '/basic-auth/user1/password1',
      'status': HTTPStatus.UNAUTHORIZED},
     'GET', '/basic-auth/user1/password1', True),
    ({'verb': 'GET', 'path': '/drip', 'status': HTTPStatus.OK},
     'GET', '/drip', True),
    ({'verb': 'GET', 'path': '/404', 'status': HTTPStatus.NOT_FOUND},
     'GET', '/404', True),

    ({'verb': 'GET', 'path': '/', 'status': HTTPStatus.OK},
     'GET', '/foo', False),
    ({'verb': 'POST', 'path': '/', 'status': HTTPStatus.OK},
     'GET', '/', False),
    ({'verb': 'GET', 'path': '/basic-auth/user/password',
      'status': HTTPStatus.UNAUTHORIZED},
     'GET', '/basic-auth/user/passwd', False),
])
def test_expected_request(server, line, verb, path, equal):
    expected = server.ExpectedRequest(verb, path)
    request = server.Request(json.dumps(line))
    assert (expected == request) == equal
