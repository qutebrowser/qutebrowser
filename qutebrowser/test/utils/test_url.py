# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# pylint: disable=protected-access

"""Tests for qutebrowser.utils.url."""

import unittest

from PyQt5.QtCore import QUrl

from qutebrowser.utils import url as urlutils
from qutebrowser.test import stubs


CONFIG = {
    'general': {'auto-search': True},
    'searchengines': {
        'test': 'http://www.qutebrowser.org/?q={}',
        'DEFAULT': 'http://www.example.com/?q={}',
    },
}


class SpecialURLTests(unittest.TestCase):

    """Test is_special_url.

    Attributes:
        SPECIAL_URLS: URLs which are special.
        NORMAL_URLS: URLs which are not special.
    """

    SPECIAL_URLS = (
        'file:///tmp/foo',
        'about:blank',
        'qute:version'
    )

    NORMAL_URLS = (
        'http://www.qutebrowser.org/',
        'www.qutebrowser.org'
    )

    def test_special_urls(self):
        """Test special URLs."""
        for url in self.SPECIAL_URLS:
            with self.subTest(url=url):
                u = QUrl(url)
                self.assertTrue(urlutils.is_special_url(u))

    def test_normal_urls(self):
        """Test non-special URLs."""
        for url in self.NORMAL_URLS:
            with self.subTest(url=url):
                u = QUrl(url)
                self.assertFalse(urlutils.is_special_url(u))


class SearchUrlTests(unittest.TestCase):

    """Test _get_search_url.

    Attributes:
        config: The urlutils.config instance.
    """

    def setUp(self):
        self.config = urlutils.config
        urlutils.config = stubs.ConfigStub(CONFIG)

    def test_default_engine(self):
        """Test default search engine."""
        url = urlutils._get_search_url('testfoo')
        self.assertEqual(url.host(), 'www.example.com')
        self.assertEqual(url.query(), 'q=testfoo')

    def test_engine_post(self):
        """Test search engine with an appended !hasbang."""
        url = urlutils._get_search_url('testfoo !test')
        self.assertEqual(url.host(), 'www.qutebrowser.org')
        self.assertEqual(url.query(), 'q=testfoo')

    def test_engine_pre(self):
        """Test search engine with a prepended !hasbang."""
        url = urlutils._get_search_url('!test testfoo')
        self.assertEqual(url.host(), 'www.qutebrowser.org')
        self.assertEqual(url.query(), 'q=testfoo')

    def test_engine_wrong(self):
        """Test with wrong search engine."""
        with self.assertRaises(urlutils.FuzzyUrlError):
            _ = urlutils._get_search_url('!blub testfoo')

    def tearDown(self):
        urlutils.config = self.config


@unittest.mock.patch('qutebrowser.utils.url.config.get', autospec=True)
class IsUrlTests(unittest.TestCase):

    """Tests for is_url.

    Class attributes:
        URLS: A list of strings which are URLs.
        NOT_URLS: A list of strings which aren't URLs.
    """

    URLS = (
        'http://foobar',
        'localhost:8080',
        'qutebrowser.org',
    )

    NOT_URLS = (
        'foo bar',
        'localhost test',
        'another . test',
        'foo',
    )

    def test_urls(self, configmock):
        """Test things which are URLs."""
        configmock.return_value = 'naive'
        for url in self.URLS:
            with self.subTest(url=url):
                self.assertTrue(urlutils.is_url(url), url)

    def test_not_urls(self, configmock):
        """Test things which are not URLs."""
        configmock.return_value = 'naive'
        for url in self.NOT_URLS:
            with self.subTest(url=url):
                self.assertFalse(urlutils.is_url(url), url)


if __name__ == '__main__':
    unittest.main()
