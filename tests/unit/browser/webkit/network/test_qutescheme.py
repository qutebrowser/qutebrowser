# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Daniel Schadt
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
import logging

from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QNetworkRequest, QNetworkReply

from qutebrowser.browser import pdfjs
from qutebrowser.browser.webkit.network import qutescheme


@pytest.fixture
def handler():
    return qutescheme.QuteSchemeHandler(win_id=0)


class TestPDFJSHandler:
    """Test the qute://pdfjs endpoint."""

    @pytest.fixture(autouse=True)
    def fake_pdfjs(self, monkeypatch):
        def get_pdfjs_res(path):
            if path == '/existing/file':
                return b'foobar'
            raise pdfjs.PDFJSNotFound(path)

        monkeypatch.setattr('qutebrowser.browser.pdfjs.get_pdfjs_res',
                            get_pdfjs_res)

    def test_existing_resource(self, handler):
        """Test with a resource that exists."""
        req = QNetworkRequest(QUrl('qute://pdfjs/existing/file'))
        reply = handler.createRequest(None, req, None)
        assert reply.readAll() == b'foobar'

    def test_nonexisting_resource(self, handler, caplog):
        """Test with a resource that does not exist."""
        req = QNetworkRequest(QUrl('qute://pdfjs/no/file'))
        with caplog.at_level(logging.WARNING, 'misc'):
            reply = handler.createRequest(None, req, None)
        assert reply.error() == QNetworkReply.ContentNotFoundError
        assert len(caplog.records) == 1
        assert (caplog.records[0].message ==
                'pdfjs resource requested but not found: /no/file')
