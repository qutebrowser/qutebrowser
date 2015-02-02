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

# pylint: disable=protected-access

"""Tests for qutebrowser.utils.urlutils."""

import unittest

from PyQt5.QtCore import QUrl

from qutebrowser.utils import urlutils
from qutebrowser.test import stubs


def get_config_stub(auto_search=True):
    """Get a config stub.

    Args:
        auto_search: The value auto-search should have.
    """
    return {
        'general': {'auto-search': auto_search},
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
        urlutils.config = stubs.ConfigStub(get_config_stub())

    def test_default_engine(self):
        """Test default search engine."""
        url = urlutils._get_search_url('testfoo')
        self.assertEqual(url.host(), 'www.example.com')
        self.assertEqual(url.query(), 'q=testfoo')

    def test_engine_pre(self):
        """Test first word is search engine name"""
        url = urlutils._get_search_url('test testfoo')
        self.assertEqual(url.host(), 'www.qutebrowser.org')
        self.assertEqual(url.query(), 'q=testfoo')

    def test_engine_pre_multiple_words(self):
        """Test first word is search engine name"""
        url = urlutils._get_search_url('test testfoo bar foo')
        self.assertEqual(url.host(), 'www.qutebrowser.org')
        self.assertEqual(url.query(), 'q=testfoo bar foo')

    def test_engine_pre_whitespace_at_end(self):
        """Test first word is search engine name"""
        url = urlutils._get_search_url('test testfoo ')
        self.assertEqual(url.host(), 'www.qutebrowser.org')
        self.assertEqual(url.query(), 'q=testfoo')

    def test_engine_with_bang_pre(self):
        """Test search engine with a prepended !hasbang."""
        url = urlutils._get_search_url('!python testfoo')
        self.assertEqual(url.host(), 'www.example.com')
        self.assertEqual(url.query(), 'q=%21python testfoo')

    def test_engine_wrong(self):
        """Test with wrong search engine."""
        url = urlutils._get_search_url('blub testfoo')
        self.assertEqual(url.host(), 'www.example.com')
        self.assertEqual(url.query(), 'q=blub testfoo')

    def tearDown(self):
        urlutils.config = self.config


class IsUrlTests(unittest.TestCase):

    """Tests for is_url.

    Class attributes:
        URLS: A list of strings which are URLs.
        NOT_URLS: A list of strings which aren't URLs.

    Attributes:
        config: The urlutils.config instance.
    """

    URLS = (
        'http://foobar',
        'localhost:8080',
        'qutebrowser.org',
        ' qutebrowser.org ',
        '127.0.0.1',
        '::1',
        '2001:41d0:2:6c11::1',
        '94.23.233.17',
        'http://user:password@qutebrowser.org/foo?bar=baz#fish',
    )

    NOT_URLS = (
        'foo bar',
        'localhost test',
        'another . test',
        'foo',
        'this is: not an URL',
        '23.42',
        '1337',
        'deadbeef',
        '31c3',
        'http:foo:0',
    )

    def setUp(self):
        self.config = urlutils.config

    def test_urls(self):
        """Test things which are URLs."""
        urlutils.config = stubs.ConfigStub(get_config_stub('naive'))
        for url in self.URLS:
            with self.subTest(url=url):
                self.assertTrue(urlutils.is_url(url), url)

    def test_not_urls(self):
        """Test things which are not URLs."""
        urlutils.config = stubs.ConfigStub(get_config_stub('naive'))
        for url in self.NOT_URLS:
            with self.subTest(url=url):
                self.assertFalse(urlutils.is_url(url), url)

    def test_search_autosearch(self):
        """Test explicit search with auto-search=True"""
        urlutils.config = stubs.ConfigStub(get_config_stub(True))
        self.assertFalse(urlutils.is_url('test foo'))

    def test_search_no_autosearch(self):
        """Test explicit search with auto-search=False"""
        urlutils.config = stubs.ConfigStub(get_config_stub(False))
        self.assertFalse(urlutils.is_url('test foo'))

    def tearDown(self):
        urlutils.config = self.config


class QurlFromUserInputTests(unittest.TestCase):

    """Tests for qurl_from_user_input."""

    def test_url(self):
        """Test a normal URL."""
        self.assertEqual(
            urlutils.qurl_from_user_input('qutebrowser.org').toString(),
            'http://qutebrowser.org')

    def test_url_http(self):
        """Test a normal URL with http://."""
        self.assertEqual(
            urlutils.qurl_from_user_input('http://qutebrowser.org').toString(),
            'http://qutebrowser.org')

    def test_ipv6_bare(self):
        """Test an IPv6 without brackets."""
        self.assertEqual(urlutils.qurl_from_user_input('::1/foo').toString(),
                         'http://[::1]/foo')

    def test_ipv6(self):
        """Test an IPv6 with brackets."""
        self.assertEqual(urlutils.qurl_from_user_input('[::1]/foo').toString(),
                         'http://[::1]/foo')

    def test_ipv6_http(self):
        """Test an IPv6 with http:// and brackets."""
        self.assertEqual(
            urlutils.qurl_from_user_input('http://[::1]').toString(),
            'http://[::1]')


class FilenameFromUrlTests(unittest.TestCase):

    """Tests for filename_from_url."""

    def test_invalid_url(self):
        """Test with an invalid QUrl."""
        self.assertEqual(urlutils.filename_from_url(QUrl()), None)

    def test_url_path(self):
        """Test with an URL with path."""
        url = QUrl('http://qutebrowser.org/test.html')
        self.assertEqual(urlutils.filename_from_url(url), 'test.html')

    def test_url_host(self):
        """Test with an URL with no path."""
        url = QUrl('http://qutebrowser.org/')
        self.assertEqual(urlutils.filename_from_url(url),
                         'qutebrowser.org.html')


if __name__ == '__main__':
    unittest.main()
