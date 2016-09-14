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

from qutebrowser.browser import pdfjs, qutescheme
# pylint: disable=unused-import
from qutebrowser.browser.webkit.network import webkitqutescheme
# pylint: enable=unused-import


class TestPDFJSHandler:
    """Test the qute://pdfjs endpoint."""

    @pytest.fixture(autouse=True)
    def fake_pdfjs(self, monkeypatch):
        def get_pdfjs_res(path):
            if path == '/existing/file.html':
                return b'foobar'
            raise pdfjs.PDFJSNotFound(path)

        monkeypatch.setattr('qutebrowser.browser.pdfjs.get_pdfjs_res',
                            get_pdfjs_res)

    @pytest.fixture(autouse=True)
    def patch_args(self, fake_args):
        fake_args.backend = 'webkit'

    def test_existing_resource(self):
        """Test with a resource that exists."""
        _mimetype, data = qutescheme.data_for_url(
            QUrl('qute://pdfjs/existing/file.html'))
        assert data == b'foobar'

    def test_nonexisting_resource(self, caplog):
        """Test with a resource that does not exist."""
        with caplog.at_level(logging.WARNING, 'misc'):
            with pytest.raises(qutescheme.QuteSchemeError):
                qutescheme.data_for_url(QUrl('qute://pdfjs/no/file.html'))
        assert len(caplog.records) == 1
        assert (caplog.records[0].message ==
                'pdfjs resource requested but not found: /no/file.html')
