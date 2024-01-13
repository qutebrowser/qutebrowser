# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
    with qtbot.wait_signal(server.new_request, timeout=100):
        url = 'http://localhost:{}{}'.format(server.port, path)
        try:
            with urllib.request.urlopen(url) as response:
                data = response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            # "Though being an exception (a subclass of URLError), an HTTPError
            # can also function as a non-exceptional file-like return value
            # (the same thing that urlopen() returns)."
            # ...wat
            print(e.read().decode('utf-8'))
            raise

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
