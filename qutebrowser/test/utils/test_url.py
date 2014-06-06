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

# pylint: disable=missing-docstring,protected-access

"""Tests for qutebrowser.utils.url."""

import unittest
from unittest import TestCase

from PyQt5.QtCore import QUrl

import qutebrowser.utils.url as urlutils


class ConfigStub:

    """Stub which is used to mock out the config.

    Attributes:
        _DATA: The config data to use
    """

    _DATA = {
        'general': {'auto-search': True},
        'searchengines': {
            'test': 'http://www.qutebrowser.org/?q={}',
            'DEFAULT': 'http://www.example.com/?q={}',
        },
    }

    class NoOptionError(Exception):

        """NoOptionError exception which does nothing."""

        pass

    def get(self, section, option):
        """Get a value from section/option.

        Raise:
            NoOptionError if the option was not found.
        """
        sect = self._DATA[section]
        try:
            return sect[option]
        except KeyError:
            raise self.NoOptionError


class ConversionTests(TestCase):

    """Test conversions between QUrl and url string.

    Attributes:
        URL: The URL to check conversion with.
    """

    URL = 'http://www.qutebrowser.org/'

    def test_qurl2qurl(self):
        """Test converting a QUrl to a QUrl."""
        q = urlutils.qurl(QUrl(self.URL))
        self.assertIsInstance(q, QUrl)
        self.assertFalse(q.isEmpty())

    def test_str2qurl(self):
        """Test converting a string to a QUrl."""
        q = urlutils.qurl(self.URL)
        self.assertIsInstance(q, QUrl)
        self.assertFalse(q.isEmpty())

    def test_str2str(self):
        """Test converting a string to a string."""
        s = urlutils.urlstring(self.URL)
        self.assertIsInstance(s, str)
        self.assertEqual(s, self.URL)

    def test_qurl2str(self):
        """Test converting a QUrl to a string."""
        s = urlutils.urlstring(QUrl(self.URL))
        self.assertIsInstance(s, str)
        self.assertEqual(s, self.URL)


class SpecialURLTests(TestCase):

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
            self.assertTrue(urlutils.is_special_url(url))

    def test_normal_urls(self):
        """Test non-special URLs."""
        for url in self.NORMAL_URLS:
            self.assertFalse(urlutils.is_special_url(url))


class SearchUrlTests(TestCase):

    """Test _get_search_url.

    Attributes:
        config: The urlutils.config instance.
    """

    def setUp(self):
        self.config = urlutils.config
        urlutils.config = ConfigStub()

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
        with self.assertRaises(urlutils.SearchEngineError):
            _ = urlutils._get_search_url('!blub testfoo')

    def tearDown(self):
        urlutils.config = self.config


class IsUrlNaiveTests(TestCase):

    """Tests for _is_url_naive.

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

    def test_urls(self):
        """Test things which are URLs."""
        for url in self.URLS:
            self.assertTrue(urlutils._is_url_naive(url), url)

    def test_not_urls(self):
        """Test things which are not URLs."""
        for url in self.NOT_URLS:
            self.assertFalse(urlutils._is_url_naive(url), url)


if __name__ == '__main__':
    unittest.main()
