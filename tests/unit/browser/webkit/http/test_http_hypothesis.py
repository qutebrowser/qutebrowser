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

import logging

import pytest
import hypothesis
from hypothesis import strategies

from qutebrowser.browser.webkit import http, rfc6266


@pytest.mark.parametrize('template', [
    '{}',
    'attachment; filename="{}"',
    'inline; {}',
    'attachment; {}="foo"',
    "attachment; filename*=iso-8859-1''{}",
    'attachment; filename*={}',
])
@hypothesis.given(strategies.text(alphabet=[chr(x) for x in range(255)]))
def test_parse_content_disposition(caplog, template, stubs, s):
    """Test parsing headers based on templates which hypothesis completes."""
    header = template.format(s)
    reply = stubs.FakeNetworkReply(headers={'Content-Disposition': header})
    with caplog.at_level(logging.ERROR, 'rfc6266'):
        http.parse_content_disposition(reply)


@hypothesis.given(strategies.binary())
def test_content_disposition_directly(s):
    """Test rfc6266.parse_headers directly with binary data."""
    try:
        cd = rfc6266.parse_headers(s)
        cd.filename()
    except (SyntaxError, UnicodeDecodeError, rfc6266.Error):
        pass


@hypothesis.given(strategies.text())
def test_parse_content_type(stubs, s):
    reply = stubs.FakeNetworkReply(headers={'Content-Type': s})
    http.parse_content_type(reply)
