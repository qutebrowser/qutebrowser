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

"""Tests for browser.network.networkreply."""

import pytest

from PyQt5.QtCore import QUrl, QIODevice
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply

from qutebrowser.browser.webkit.network import networkreply


@pytest.fixture
def req():
    return QNetworkRequest(QUrl('http://www.qutebrowser.org/'))


class TestFixedDataNetworkReply:

    def test_attributes(self, req):
        reply = networkreply.FixedDataNetworkReply(req, b'', 'test/foo')
        assert reply.request() == req
        assert reply.url() == req.url()
        assert reply.openMode() == QIODevice.ReadOnly
        assert reply.header(QNetworkRequest.ContentTypeHeader) == 'test/foo'
        http_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        http_reason = reply.attribute(
            QNetworkRequest.HttpReasonPhraseAttribute)
        assert http_code == 200
        assert http_reason == 'OK'
        assert reply.isFinished()
        assert not reply.isRunning()

    @pytest.mark.parametrize('data', [b'', b'foobar',
                                      b'Hello World! This is a test.'])
    def test_data(self, qtbot, req, data):
        reply = networkreply.FixedDataNetworkReply(req, data, 'test/foo')
        with qtbot.waitSignals([reply.metaDataChanged, reply.readyRead,
                                reply.finished], order='strict'):
            pass

        assert reply.bytesAvailable() == len(data)
        assert reply.readAll() == data

    @pytest.mark.parametrize('chunk_size', [1, 2, 3])
    def test_data_chunked(self, chunk_size, req):
        data = b'123'
        reply = networkreply.FixedDataNetworkReply(req, data, 'test/foo')
        while data:
            assert reply.bytesAvailable() == len(data)
            assert reply.readData(chunk_size) == data[:chunk_size]
            data = data[chunk_size:]

    def test_abort(self, req):
        reply = networkreply.FixedDataNetworkReply(req, b'foo', 'test/foo')
        reply.abort()
        assert reply.readAll() == b'foo'


def test_error_network_reply(qtbot, req):
    reply = networkreply.ErrorNetworkReply(
        req, "This is an error", QNetworkReply.UnknownNetworkError)

    with qtbot.waitSignals([reply.error, reply.finished], order='strict'):
        pass

    reply.abort()  # shouldn't do anything
    assert reply.request() == req
    assert reply.url() == req.url()
    assert reply.openMode() == QIODevice.ReadOnly
    assert reply.isFinished()
    assert not reply.isRunning()
    assert reply.bytesAvailable() == 0
    assert reply.readData(1) == b''
    assert reply.error() == QNetworkReply.UnknownNetworkError
    assert reply.errorString() == "This is an error"


def test_redirect_network_reply():
    url = QUrl('https://www.example.com/')
    reply = networkreply.RedirectNetworkReply(url)
    assert reply.readData(1) == b''
    assert reply.attribute(QNetworkRequest.RedirectionTargetAttribute) == url
    reply.abort()  # shouldn't do anything
