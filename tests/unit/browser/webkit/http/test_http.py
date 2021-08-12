# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for qutebrowser.browser.webkit.http."""

import logging

import pytest
import hypothesis
from hypothesis import strategies
from PyQt5.QtCore import QUrl

from qutebrowser.browser.webkit import http


@pytest.mark.parametrize('url, expected', [
    # Filename in the URL
    ('http://example.com/path', 'path'),
    ('http://example.com/foo/path', 'path'),
    # No filename at all
    ('http://example.com', 'qutebrowser-download'),
    ('http://example.com/', 'qutebrowser-download'),
])
def test_no_content_disposition(stubs, url, expected):
    reply = stubs.FakeNetworkReply(url=QUrl(url))
    inline, filename = http.parse_content_disposition(reply)
    assert inline
    assert filename == expected


@pytest.mark.parametrize('template', [
    '{}',
    'attachment; filename="{}"',
    'inline; {}',
    'attachment; {}="foo"',
    "attachment; filename*=iso-8859-1''{}",
    'attachment; filename*={}',
])
@hypothesis.given(strategies.text(alphabet=[chr(x) for x in range(255)]))
def test_parse_content_disposition_hypothesis(caplog, template, stubs, s):
    """Test parsing headers based on templates which hypothesis completes."""
    header = template.format(s)
    reply = stubs.FakeNetworkReply(headers={'Content-Disposition': header})
    with caplog.at_level(logging.ERROR, 'network'):
        http.parse_content_disposition(reply)


@hypothesis.given(strategies.binary())
def test_content_disposition_directly_hypothesis(s):
    """Test rfc6266 parsing directly with binary data."""
    try:
        cd = http.ContentDisposition.parse(s)
        cd.filename()
    except http.ContentDispositionError:
        pass


@pytest.mark.parametrize('content_type, expected_mimetype, expected_rest', [
    (None, None, None),
    ('image/example', 'image/example', None),
    ('', '', None),
    ('image/example; encoding=UTF-8', 'image/example', ' encoding=UTF-8'),
])
def test_parse_content_type(stubs, content_type, expected_mimetype,
                            expected_rest):
    if content_type is None:
        reply = stubs.FakeNetworkReply()
    else:
        reply = stubs.FakeNetworkReply(headers={'Content-Type': content_type})
    mimetype, rest = http.parse_content_type(reply)
    assert mimetype == expected_mimetype
    assert rest == expected_rest


@hypothesis.given(strategies.text())
def test_parse_content_type_hypothesis(stubs, s):
    reply = stubs.FakeNetworkReply(headers={'Content-Type': s})
    http.parse_content_type(reply)
