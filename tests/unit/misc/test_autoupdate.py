# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Alexander Cogneau (acogneau) <alexander.cogneau@gmail.com>:
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

"""Tests for qutebrowser.misc.autoupdate"""

from PyQt5.QtTest import QSignalSpy

from qutebrowser.misc import autoupdate, httpclient


class HTTPGetStub(httpclient.HTTPClient):
    """A stub class for HTTPClient.

        Attributes:
        _success: Wether get() will emit a success signal.
    """

    def __init__(self, success=True, json=None):
        self._success = success
        if json:
            self._json = json
        else:
            self._json = '{"info": {"version": "test"}}'

        super(HTTPGetStub, self).__init__()

    def get(self, url):
        if self._success is True:
            self.success.emit(self._json)
        else:
            self.error.emit("error")


def test_constructor():
    client = autoupdate.PyPIVersionClient()
    assert isinstance(client._client, httpclient.HTTPClient)


def test_get_version_success(qtbot):
    """Test get_version() when success is emitted."""
    http_stub = HTTPGetStub(success=True)
    client = autoupdate.PyPIVersionClient(client=http_stub)

    # Use a spy to inspect the signal
    success_spy = QSignalSpy(client.success)
    error_spy = QSignalSpy(client.error)

    with qtbot.waitSignal(client.success, timeout=2000, raising=False):
        client.get_version('test')

    assert len(success_spy) == 1
    assert len(error_spy) == 0


def test_get_version_error(qtbot):
    """Test get_version() when error is emitted."""
    http_stub = HTTPGetStub(success=False)
    client = autoupdate.PyPIVersionClient(client=http_stub)

    # Use a spy to inspect the signal
    success_spy = QSignalSpy(client.success)
    error_spy = QSignalSpy(client.error)

    with qtbot.waitSignal(client.error, timeout=2000, raising=False):
        client.get_version('test')

    assert len(success_spy) == 0
    assert len(error_spy) == 1


def test_invalid_json():
    """Test on_client_success() with invalid JSON."""
    json = '{"invalid": { "json"}'
    http_stub = HTTPGetStub(json=json)
    client = autoupdate.PyPIVersionClient(client=http_stub)
    error_spy = QSignalSpy(client.error)
    client.get_version('test')
    assert len(error_spy) == 1


def test_invalid_keys():
    """Test on_client_success() with valid JSON and wrong keys."""
    json = '{"wrong": "keys"}'
    http_stub = HTTPGetStub(json=json)
    client = autoupdate.PyPIVersionClient(client=http_stub)
    error_spy = QSignalSpy(client.error)
    client.get_version('test')
    assert len(error_spy) == 1
