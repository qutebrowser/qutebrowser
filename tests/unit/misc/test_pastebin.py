# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The-Compiler) <me@the-compiler.org>
# Copyright 2016-2018 Anna Kobak (avk) <awerk@onet.eu>:
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

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.misc import httpclient, pastebin


@pytest.fixture
def pbclient(stubs):
    http_stub = stubs.HTTPPostStub()
    client = pastebin.PastebinClient(http_stub)
    return client


def test_constructor(qapp):
    http_client = httpclient.HTTPClient()
    pastebin.PastebinClient(http_client)


@pytest.mark.parametrize('data', [
    {
        "name": "XYZ",
        "title": "hello world",
        "text": "xyz. 123 \n 172ANB",
        "reply": "abc",
        "apikey": "ihatespam",
    },
    {
        "name": "the name",
        "title": "the title",
        "text": "some Text",
        "reply": "some parent",
        "apikey": "ihatespam",
    }
])
def test_paste_with_parent(data, pbclient):
    http_stub = pbclient._client
    pbclient.paste(data["name"], data["title"], data["text"], data["reply"])
    assert http_stub.data == data
    assert http_stub.url == QUrl('https://crashes.qutebrowser.org/api/create')


@pytest.mark.parametrize('data', [
    {
        "name": "XYZ",
        "title": "hello world",
        "text": "xyz. 123 \n 172ANB",
        "apikey": "ihatespam",
    },
    {
        "name": "the name",
        "title": "the title",
        "text": "some Text",
        "apikey": "ihatespam",
    }
])
def test_paste_without_parent(data, pbclient):
    http_stub = pbclient._client
    pbclient.paste(data["name"], data["title"], data["text"])
    assert pbclient._client.data == data
    assert http_stub.url == QUrl('https://crashes.qutebrowser.org/api/create')


def test_paste_private(pbclient):
    data = {
        "name": "the name",
        "title": "the title",
        "text": "some Text",
        "apikey": "ihatespam",
        "private": "1",
    }
    http_stub = pbclient._client
    pbclient.paste(data["name"], data["title"], data["text"], private=True)
    assert pbclient._client.data == data
    assert http_stub.url == QUrl('https://crashes.qutebrowser.org/api/create')


@pytest.mark.parametrize('http', [
    "http://paste.the-compiler.org/view/ges83nt3",
    "http://paste.the-compiler.org/view/3gjnwg4"
])
def test_on_client_success(http, pbclient, qtbot):
    with qtbot.assertNotEmitted(pbclient.error):
        with qtbot.waitSignal(pbclient.success):
            pbclient._client.success.emit(http)


@pytest.mark.parametrize('http', [
    "http invalid",
    "http:/invalid.org"
    "http//invalid.com"
])
def test_client_success_invalid_http(http, pbclient, qtbot):
    with qtbot.assertNotEmitted(pbclient.success):
        with qtbot.waitSignal(pbclient.error):
            pbclient._client.success.emit(http)


def test_client_error(pbclient, qtbot):
    with qtbot.assertNotEmitted(pbclient.success):
        with qtbot.waitSignal(pbclient.error):
            pbclient._client.error.emit("msg")
