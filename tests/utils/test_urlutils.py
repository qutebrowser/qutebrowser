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

from PyQt5.QtCore import QUrl
import pytest

from qutebrowser.utils import urlutils


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


class TestSpecialURL:

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

    @pytest.mark.parametrize('url', SPECIAL_URLS)
    def test_special_urls(self, url):
        """Test special URLs."""
        u = QUrl(url)
        assert urlutils.is_special_url(u)

    @pytest.mark.parametrize('url', NORMAL_URLS)
    def test_normal_urls(self, url):
        """Test non-special URLs."""
        u = QUrl(url)
        assert not urlutils.is_special_url(u)


class TestSearchUrl:

    """Test _get_search_url."""

    @pytest.fixture(autouse=True)
    def mock_config(self, stubs, mocker):
        """Fixture to patch urlutils.config with a stub."""
        mocker.patch('qutebrowser.utils.urlutils.config',
                     new=stubs.ConfigStub(get_config_stub()))

    def test_default_engine(self):
        """Test default search engine."""
        url = urlutils._get_search_url('testfoo')
        assert url.host() == 'www.example.com'
        assert url.query() == 'q=testfoo'

    def test_engine_pre(self):
        """Test search engine name with one word."""
        url = urlutils._get_search_url('test testfoo')
        assert url.host() == 'www.qutebrowser.org'
        assert url.query() == 'q=testfoo'

    def test_engine_pre_multiple_words(self):
        """Test search engine name with multiple words."""
        url = urlutils._get_search_url('test testfoo bar foo')
        assert url.host() == 'www.qutebrowser.org'
        assert url.query() == 'q=testfoo bar foo'

    def test_engine_pre_whitespace_at_end(self):
        """Test search engine name with one word and whitespace."""
        url = urlutils._get_search_url('test testfoo ')
        assert url.host() == 'www.qutebrowser.org'
        assert url.query() == 'q=testfoo'

    def test_engine_with_bang_pre(self):
        """Test search engine with a prepended !bang."""
        url = urlutils._get_search_url('!python testfoo')
        assert url.host() == 'www.example.com'
        assert url.query() == 'q=%21python testfoo'

    def test_engine_wrong(self):
        """Test with wrong search engine."""
        url = urlutils._get_search_url('blub testfoo')
        assert url.host() == 'www.example.com'
        assert url.query() == 'q=blub testfoo'


class TestIsUrl:

    """Tests for is_url.

    Class attributes:
        URLS: A list of strings which are URLs.
        NOT_URLS: A list of strings which aren't URLs.
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
        'foo::bar',
    )

    @pytest.mark.parametrize('url', URLS)
    def test_urls(self, mocker, stubs, url):
        """Test things which are URLs."""
        mocker.patch('qutebrowser.utils.urlutils.config', new=stubs.ConfigStub(
            get_config_stub('naive')))
        assert urlutils.is_url(url), url

    @pytest.mark.parametrize('url', NOT_URLS)
    def test_not_urls(self, mocker, stubs, url):
        """Test things which are not URLs."""
        mocker.patch('qutebrowser.utils.urlutils.config', new=stubs.ConfigStub(
            get_config_stub('naive')))
        assert not urlutils.is_url(url), url

    @pytest.mark.parametrize('autosearch', [True, False])
    def test_search_autosearch(self, mocker, stubs, autosearch):
        """Test explicit search with auto-search=True."""
        mocker.patch('qutebrowser.utils.urlutils.config', new=stubs.ConfigStub(
            get_config_stub(autosearch)))
        assert not urlutils.is_url('test foo')


class TestQurlFromUserInput:

    """Tests for qurl_from_user_input."""

    def test_url(self):
        """Test a normal URL."""
        url = urlutils.qurl_from_user_input('qutebrowser.org')
        assert url.toString() == 'http://qutebrowser.org'

    def test_url_http(self):
        """Test a normal URL with http://."""
        url = urlutils.qurl_from_user_input('http://qutebrowser.org')
        assert url.toString() == 'http://qutebrowser.org'

    def test_ipv6_bare(self):
        """Test an IPv6 without brackets."""
        url = urlutils.qurl_from_user_input('::1/foo')
        assert url.toString() == 'http://[::1]/foo'

    def test_ipv6(self):
        """Test an IPv6 with brackets."""
        url = urlutils.qurl_from_user_input('[::1]/foo')
        assert url.toString() == 'http://[::1]/foo'

    def test_ipv6_http(self):
        """Test an IPv6 with http:// and brackets."""
        url = urlutils.qurl_from_user_input('http://[::1]')
        assert url.toString() == 'http://[::1]'


class TestFilenameFromUrl:

    """Tests for filename_from_url."""

    def test_invalid_url(self):
        """Test with an invalid QUrl."""
        assert urlutils.filename_from_url(QUrl()) is None

    def test_url_path(self):
        """Test with an URL with path."""
        url = QUrl('http://qutebrowser.org/test.html')
        assert urlutils.filename_from_url(url) == 'test.html'

    def test_url_host(self):
        """Test with an URL with no path."""
        url = QUrl('http://qutebrowser.org/')
        assert urlutils.filename_from_url(url) == 'qutebrowser.org.html'
