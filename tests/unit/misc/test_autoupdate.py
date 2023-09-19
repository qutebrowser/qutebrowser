# SPDX-FileCopyrightText: Alexander Cogneau (acogneau) <alexander.cogneau@gmail.com>:
# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.misc.autoupdate."""

import pytest
from qutebrowser.qt.core import QUrl

from qutebrowser.misc import autoupdate, httpclient

INVALID_JSON = ['{"invalid": { "json"}', '{"wrong": "keys"}']


class HTTPGetStub(httpclient.HTTPClient):

    """A stub class for HTTPClient.

    Attributes:
        url: the last url used by get()
        _success: Whether get() will emit a success signal.
    """

    def __init__(self, success=True, json=None):
        super().__init__()
        self.url = None
        self._success = success
        if json:
            self._json = json
        else:
            self._json = '{"info": {"version": "test"}}'

    def get(self, url):
        self.url = url
        if self._success:
            self.success.emit(self._json)
        else:
            self.error.emit("error")


def test_constructor(qapp):
    client = autoupdate.PyPIVersionClient()
    assert isinstance(client._client, httpclient.HTTPClient)


def test_get_version_success(qtbot):
    """Test get_version() when success is emitted."""
    http_stub = HTTPGetStub(success=True)
    client = autoupdate.PyPIVersionClient(client=http_stub)

    with qtbot.assert_not_emitted(client.error):
        with qtbot.wait_signal(client.success):
            client.get_version('test')

    assert http_stub.url == QUrl(client.API_URL.format('test'))


def test_get_version_error(qtbot):
    """Test get_version() when error is emitted."""
    http_stub = HTTPGetStub(success=False)
    client = autoupdate.PyPIVersionClient(client=http_stub)

    with qtbot.assert_not_emitted(client.success):
        with qtbot.wait_signal(client.error):
            client.get_version('test')


@pytest.mark.parametrize('json', INVALID_JSON)
def test_invalid_json(qtbot, json):
    """Test on_client_success() with invalid JSON."""
    http_stub = HTTPGetStub(json=json)
    client = autoupdate.PyPIVersionClient(client=http_stub)
    client.get_version('test')

    with qtbot.assert_not_emitted(client.success):
        with qtbot.wait_signal(client.error):
            client.get_version('test')
