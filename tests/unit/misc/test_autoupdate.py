# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2015-2018 Alexander Cogneau (acogneau) <alexander.cogneau@gmail.com>:
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

"""Tests for qutebrowser.misc.autoupdate."""

import pytest
from PyQt5.QtCore import QUrl

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

    with qtbot.assertNotEmitted(client.error):
        with qtbot.waitSignal(client.success):
            client.get_version('test')

    assert http_stub.url == QUrl(client.API_URL.format('test'))


def test_get_version_error(qtbot):
    """Test get_version() when error is emitted."""
    http_stub = HTTPGetStub(success=False)
    client = autoupdate.PyPIVersionClient(client=http_stub)

    with qtbot.assertNotEmitted(client.success):
        with qtbot.waitSignal(client.error):
            client.get_version('test')


@pytest.mark.parametrize('json', INVALID_JSON)
def test_invalid_json(qtbot, json):
    """Test on_client_success() with invalid JSON."""
    http_stub = HTTPGetStub(json=json)
    client = autoupdate.PyPIVersionClient(client=http_stub)
    client.get_version('test')

    with qtbot.assertNotEmitted(client.success):
        with qtbot.waitSignal(client.error):
            client.get_version('test')
