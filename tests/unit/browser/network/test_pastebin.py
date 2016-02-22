# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Anna Kobak (avk) <arsana7@gmail.com>:
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

DATA = [{"name" : "XYZ", "title" : "hello world", "text" : "xyz. 123 \n 172ANB", "reply" : "abc" }]

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
def test_paste(data):
    client = pastebin.PastebinClient()
    http_stub = HTTPPostStub()
    client._client = http_stub
    client.paste(data["name"], data["title"], data["text"], data["reply"])
    assert http_stub.data == data
    assert http_stub.url == QUrl('http://paste.the-compiler.org/api/create')
 
