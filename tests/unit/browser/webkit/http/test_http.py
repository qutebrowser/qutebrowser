# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.browser.webkit.http.

Note that tests for parse_content_disposition are in their own
test_content_disposition.py file.
"""

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.browser.webkit import http


class TestNoContentDisposition:

    """Test parse_content_disposition with no Content-Disposition header."""

    @pytest.mark.parametrize('url', ['http://example.com/path',
                                     'http://example.com/foo/path'])
    def test_url(self, stubs, url):
        """Test with a filename in the URL."""
        reply = stubs.FakeNetworkReply(url=QUrl(url))
        inline, filename = http.parse_content_disposition(reply)
        assert inline
        assert filename == 'path'

    @pytest.mark.parametrize('url', ['http://example.com',
                                     'http://example.com/'])
    def test_none(self, stubs, url):
        """Test with no filename at all."""
        reply = stubs.FakeNetworkReply(url=QUrl(url))
        inline, filename = http.parse_content_disposition(reply)
        assert inline
        assert filename == 'qutebrowser-download'


class TestParseContentType:

    """Test for parse_content_type."""

    def test_not_existing(self, stubs):
        """Test without any Content-Type header."""
        reply = stubs.FakeNetworkReply()
        mimetype, rest = http.parse_content_type(reply)
        assert mimetype is None
        assert rest is None

    def test_mimetype(self, stubs):
        """Test with simple Content-Type header."""
        reply = stubs.FakeNetworkReply(
            headers={'Content-Type': 'image/example'})
        mimetype, rest = http.parse_content_type(reply)
        assert mimetype == 'image/example'
        assert rest is None

    def test_empty(self, stubs):
        """Test with empty Content-Type header."""
        reply = stubs.FakeNetworkReply(headers={'Content-Type': ''})
        mimetype, rest = http.parse_content_type(reply)
        assert mimetype == ''
        assert rest is None

    def test_additional(self, stubs):
        """Test with Content-Type header with additional informations."""
        reply = stubs.FakeNetworkReply(
            headers={'Content-Type': 'image/example; encoding=UTF-8'})
        mimetype, rest = http.parse_content_type(reply)
        assert mimetype == 'image/example'
        assert rest == ' encoding=UTF-8'
