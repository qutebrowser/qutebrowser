# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for browser.network.networkreply."""

import pytest

from qutebrowser.qt.core import QUrl, QIODevice
from qutebrowser.qt.network import QNetworkRequest, QNetworkReply

from qutebrowser.browser.webkit.network import networkreply


@pytest.fixture
def req():
    return QNetworkRequest(QUrl('http://www.qutebrowser.org/'))


class TestFixedDataNetworkReply:

    def test_attributes(self, req):
        reply = networkreply.FixedDataNetworkReply(req, b'', 'test/foo')
        assert reply.request() == req
        assert reply.url() == req.url()
        assert reply.openMode() == QIODevice.OpenModeFlag.ReadOnly
        assert reply.header(QNetworkRequest.KnownHeaders.ContentTypeHeader) == 'test/foo'
        http_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        http_reason = reply.attribute(
            QNetworkRequest.Attribute.HttpReasonPhraseAttribute)
        assert http_code == 200
        assert http_reason == 'OK'
        assert reply.isFinished()
        assert not reply.isRunning()

    @pytest.mark.parametrize('data', [b'', b'foobar',
                                      b'Hello World! This is a test.'])
    def test_data(self, qtbot, req, data):
        reply = networkreply.FixedDataNetworkReply(req, data, 'test/foo')
        with qtbot.wait_signals([reply.metaDataChanged, reply.readyRead,
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
        req, "This is an error", QNetworkReply.NetworkError.UnknownNetworkError)

    with qtbot.wait_signals([reply.errorOccurred, reply.finished], order='strict'):
        pass

    reply.abort()  # shouldn't do anything
    assert reply.request() == req
    assert reply.url() == req.url()
    assert reply.openMode() == QIODevice.OpenModeFlag.ReadOnly
    assert reply.isFinished()
    assert not reply.isRunning()
    assert reply.bytesAvailable() == 0
    assert reply.readData(1) == b''
    assert reply.error() == QNetworkReply.NetworkError.UnknownNetworkError
    assert reply.errorString() == "This is an error"


def test_redirect_network_reply():
    url = QUrl('https://www.example.com/')
    reply = networkreply.RedirectNetworkReply(url)
    assert reply.readData(1) == b''
    assert reply.attribute(QNetworkRequest.Attribute.RedirectionTargetAttribute) == url
    reply.abort()  # shouldn't do anything
