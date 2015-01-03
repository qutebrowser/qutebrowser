# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.utils.http.

Note that tests for parse_content_disposition are in their own
test_content_disposition.py file.
"""

import unittest

from qutebrowser.utils import http
from qutebrowser.test import stubs


class ParseContentTypeTests(unittest.TestCase):

    """Test for parse_content_type."""

    def test_not_existing(self):
        """Test without any Content-Type header."""
        reply = stubs.FakeNetworkReply()
        mimetype, rest = http.parse_content_type(reply)
        self.assertIsNone(mimetype)
        self.assertIsNone(rest)

    def test_mimetype(self):
        """Test with simple Content-Type header."""
        reply = stubs.FakeNetworkReply(
            headers={'Content-Type': 'image/example'})
        mimetype, rest = http.parse_content_type(reply)
        self.assertEqual(mimetype, 'image/example')
        self.assertIsNone(rest)

    def test_empty(self):
        """Test with empty Content-Type header."""
        reply = stubs.FakeNetworkReply(headers={'Content-Type': ''})
        mimetype, rest = http.parse_content_type(reply)
        self.assertEqual(mimetype, '')
        self.assertIsNone(rest)

    def test_additional(self):
        """Test with Content-Type header with additional informations."""
        reply = stubs.FakeNetworkReply(
            headers={'Content-Type': 'image/example; encoding=UTF-8'})
        mimetype, rest = http.parse_content_type(reply)
        self.assertEqual(mimetype, 'image/example')
        self.assertEqual(rest, ' encoding=UTF-8')


if __name__ == '__main__':
    unittest.main()
