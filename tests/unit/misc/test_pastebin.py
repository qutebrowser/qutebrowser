# SPDX-FileCopyrightText: Anna Kobak (avk) <awerk@onet.eu>:
# SPDX-FileCopyrightText: Florian Bruhin (The-Compiler) <me@the-compiler.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from qutebrowser.qt.core import QUrl

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
    with qtbot.assert_not_emitted(pbclient.error):
        with qtbot.wait_signal(pbclient.success):
            pbclient._client.success.emit(http)


@pytest.mark.parametrize('http', [
    "http invalid",
    "http:/invalid.org"
    "http//invalid.com"
])
def test_client_success_invalid_http(http, pbclient, qtbot):
    with qtbot.assert_not_emitted(pbclient.success):
        with qtbot.wait_signal(pbclient.error):
            pbclient._client.success.emit(http)


def test_client_error(pbclient, qtbot):
    with qtbot.assert_not_emitted(pbclient.success):
        with qtbot.wait_signal(pbclient.error):
            pbclient._client.error.emit("msg")
