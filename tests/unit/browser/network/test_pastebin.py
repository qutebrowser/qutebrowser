# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Anna Kobak (avk) <awerk@onet.eu>:
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

"""Tests for qutebrowser.browser.network"""

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.browser.network import pastebin
from qutebrowser.misc import httpclient

DATA = [{"name" : "XYZ", "title" : "hello world", "text" : "xyz. 123 \n 172ANB", "reply" : "abc" },
        {"name" : "the name", "title" : "the title", "text" : "some Text", "reply" : "some parent"}]

DATA_NOPARENT = [{"name" : "XYZ", "title" : "hello world", "text" : "xyz. 123 \n 172ANB"},
                 {"name" : "the name", "title" : "the title", "text" : "some Text"}]

HTTP_VALID = ["http://paste.the-compiler.org/view/ges83nt3", "http://paste.the-compiler.org/view/3gjnwg4"]

HTTP_INVALID = ["http invalid", "http:/invalid.org"]

class HTTPPostStub(httpclient.HTTPClient):

    """A stub class for HTTPClient.

    Attributes:
        url: the last url send by post()
        data: the last data send by post()
    """

    def __init__(self):
        super().__init__()
    
    def post(self, url, data):
        self.url = url
        self.data = data



def test_constructor(qapp):
    client = pastebin.PastebinClient()
    assert isinstance(client._client, httpclient.HTTPClient)

@pytest.mark.parametrize('data', DATA)
def test_paste_with_parent(data):
    client = pastebin.PastebinClient()
    http_stub = HTTPPostStub()
    client._client = http_stub
    client.paste(data["name"], data["title"], data["text"], data["reply"])
    assert http_stub.data == data
    assert http_stub.url == QUrl('http://paste.the-compiler.org/api/create')
 
@pytest.mark.parametrize('data', DATA_NOPARENT)
def test_paste_without_parent(data):
    client = pastebin.PastebinClient()
    http_stub = HTTPPostStub()
    client._client = http_stub
    client.paste(data["name"], data["title"], data["text"])
    assert http_stub.data == data
    assert http_stub.url == QUrl('http://paste.the-compiler.org/api/create')

@pytest.mark.parametrize('http', HTTP_VALID)
def test_on_client_success(http, qtbot):
    client = pastebin.PastebinClient()
    http_stub = HTTPPostStub()
    client._client = http_stub
    with qtbot.assertNotEmitted(client.error):
        with qtbot.waitSignal(client.success):
            client.on_client_success(http)

@pytest.mark.parametrize('http', HTTP_INVALID)
def test_on_client_success_invalid_http(http, qtbot):
    client = pastebin.PastebinClient()
    http_stub = HTTPPostStub()
    client._client = http_stub
    with qtbot.assertNotEmitted(client.success):
        with qtbot.waitSignal(client.error):
            client.on_client_success(http)

