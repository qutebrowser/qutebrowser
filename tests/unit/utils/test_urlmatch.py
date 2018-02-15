# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.utils.urlmatch.

The tests are mostly inspired by Chromium's:
https://cs.chromium.org/chromium/src/extensions/common/url_pattern_unittest.cc

Currently not tested:
- The match_effective_tld attribute as it doesn't exist yet.
- Nested filesystem:// URLs as we don't have those.
- Unicode matching because QUrl doesn't like those URLs.
"""

import pytest

from PyQt5.QtCore import QUrl

from qutebrowser.utils import urlmatch


@pytest.mark.parametrize('pattern, error', [
    # Chromium: PARSE_ERROR_MISSING_SCHEME_SEPARATOR
    ("http", "No scheme given"),
    ("http:", "Pattern without host"),
    ("http:/", "Pattern without host"),
    ("about://", "Pattern without path"),
    ("http:/bar", "Pattern without host"),

    # Chromium: PARSE_ERROR_EMPTY_HOST
    ("http://", "Pattern without host"),
    ("http:///", "Pattern without host"),
    ("http:// /", "Pattern without host"),

    # Chromium: PARSE_ERROR_EMPTY_PATH
    # FIXME: should we allow this or not?
    # ("http://bar", "URLPattern::"),

    # Chromium: PARSE_ERROR_INVALID_HOST
    ("http://\0www/", "May not contain NUL byte"),

    # Chromium: PARSE_ERROR_INVALID_HOST_WILDCARD
    ("http://*foo/bar", "Invalid host wildcard"),
    ("http://foo.*.bar/baz", "Invalid host wildcard"),
    ("http://fo.*.ba:123/baz", "Invalid host wildcard"),
    ("http://foo.*/bar", "TLD wildcards are not implemented yet"),

    # Chromium: PARSE_ERROR_INVALID_PORT
    ("http://foo:/", "Empty port"),
    ("http://*.foo:/", "Empty port"),
    ("http://foo:com/", "Invalid port"),
    ("http://foo:123456/", "Invalid port"),
    ("http://foo:80:80/monkey", "Invalid port"),
    ("chrome://foo:1234/bar", "Ports are unsupported with chrome scheme"),
])
def test_invalid_patterns(pattern, error):
    with pytest.raises(urlmatch.ParseError, match=error):
        urlmatch.UrlPattern(pattern)


@pytest.mark.parametrize('pattern, port', [
    ("http://foo:1234/", 1234),
    ("http://foo:1234/bar", 1234),
    ("http://*.foo:1234/", 1234),
    ("http://*.foo:1234/bar", 1234),
    # FIXME Why is this valid in Chromium?
    # ("http://:1234/", 1234),
    ("http://foo:*/", None),
    ("file://foo:1234/bar", None),

    # Port-like strings in the path should not trigger a warning.
    ("http://*/:1234", None),
    ("http://*.foo/bar:1234", None),
    ("http://foo/bar:1234/path", None),
    # We don't implement ALLOW_WILDCARD_FOR_EFFECTIVE_TLD yet.
    # ("http://*.foo.*/:1234", None),
])
def test_port(pattern, port):
    up = urlmatch.UrlPattern(pattern)
    assert up._port == port


class TestMatchAllPagesForGivenScheme:

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern("http://*/*")

    def test_attrs(self, up):
        assert up._scheme == 'http'
        assert up._host is None
        assert up._match_subdomains
        assert not up._match_all
        assert up._path is None

    @pytest.mark.parametrize('url, expected', [
        ("http://google.com", True),
        ("http://yahoo.com", True),
        ("http://google.com/foo", True),
        ("https://google.com", False),
        ("http://74.125.127.100/search", True),
    ])
    def test_urls(self, up, url, expected):
        assert up.matches(QUrl(url)) == expected


class TestMatchAllDomains:

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern("https://*/foo*")

    def test_attrs(self, up):
        assert up._scheme == 'https'
        assert up._host is None
        assert up._match_subdomains
        assert not up._match_all
        assert up._path == '/foo*'

    @pytest.mark.parametrize('url, expected', [
        ("https://google.com/foo", True),
        ("https://google.com/foobar", True),
        ("http://google.com/foo", False),
        ("https://google.com/", False),
    ])
    def test_urls(self, up, url, expected):
        assert up.matches(QUrl(url)) == expected


class TestMatchSubdomains:

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern("http://*.google.com/foo*bar")

    def test_attrs(self, up):
        assert up._scheme == 'http'
        assert up._host == 'google.com'
        assert up._match_subdomains
        assert not up._match_all
        assert up._path == '/foo*bar'

    @pytest.mark.parametrize('url, expected', [
        ("http://google.com/foobar", True),
        # FIXME The ?bar seems to be treated as path by GURL but as query by
        # QUrl.
        # ("http://www.google.com/foo?bar", True),
        ("http://monkey.images.google.com/foooobar", True),
        ("http://yahoo.com/foobar", False),
    ])
    def test_urls(self, up, url, expected):
        assert up.matches(QUrl(url)) == expected


class TestMatchGlobEscaping:

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern(r"file:///foo-bar\*baz")

    def test_attrs(self, up):
        assert up._scheme == 'file'
        assert up._host is None
        assert not up._match_subdomains
        assert not up._match_all
        assert up._path == r'/foo-bar\*baz'

    @pytest.mark.parametrize('url, expected', [
        # We use - instead of ? so it doesn't get treated as query
        (r"file:///foo-bar\hellobaz", True),
        (r"file:///fooXbar\hellobaz", False),
    ])
    def test_urls(self, up, url, expected):
        assert up.matches(QUrl(url)) == expected


class TestMatchIpAddresses:

    @pytest.mark.parametrize('pattern, host, match_subdomains', [
        ("http://127.0.0.1/*", "127.0.0.1", False),
        ("http://*.0.0.1/*", "0.0.1", True),
    ])
    def test_attrs(self, pattern, host, match_subdomains):
        up = urlmatch.UrlPattern(pattern)
        assert up._scheme == 'http'
        assert up._host == host
        assert up._match_subdomains == match_subdomains
        assert not up._match_all
        assert up._path is None

    @pytest.mark.parametrize('pattern, expected', [
        ("http://127.0.0.1/*", True),
        # No subdomain matching is done with IPs
        ("http://*.0.0.1/*", False),
    ])
    def test_urls(self, pattern, expected):
        up = urlmatch.UrlPattern(pattern)
        assert up.matches(QUrl("http://127.0.0.1")) == expected


class TestMatchChromeUrls:

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern("chrome://favicon/*")

    def test_attrs(self, up):
        assert up._scheme == 'chrome'
        assert up._host == 'favicon'
        assert not up._match_subdomains
        assert not up._match_all
        assert up._path is None

    @pytest.mark.parametrize('url, expected', [
        ("chrome://favicon/http://google.com", True),
        ("chrome://favicon/https://google.com", True),
        ("chrome://history", False),
    ])
    def test_urls(self, up, url, expected):
        assert up.matches(QUrl(url)) == expected


class TestMatchAnything:

    @pytest.fixture(params=['*://*/*', '<all_urls>'])
    def up(self, request):
        return urlmatch.UrlPattern(request.param)

    def test_attrs_common(self, up):
        assert up._scheme is None
        assert up._host is None
        assert up._path is None

    def test_attrs_wildcard(self):
        up = urlmatch.UrlPattern('*://*/*')
        assert up._match_subdomains
        assert not up._match_all

    def test_attrs_all(self):
        up = urlmatch.UrlPattern('<all_urls>')
        assert not up._match_subdomains
        assert up._match_all

    @pytest.mark.parametrize('url', [
        "http://127.0.0.1",
        # We deviate from Chromium as we allow other schemes as well
        "chrome://favicon/http://google.com",
        "file:///foo/bar",
        "file://localhost/foo/bar",
        "qute://version",
        "about:blank",
        "data:text/html;charset=utf-8,<html>asdf</html>",
    ])
    def test_urls(self, up, url):
        assert up.matches(QUrl(url))


@pytest.mark.parametrize('pattern, url, expected', [
    ("about:*", "about:blank", True),
    ("about:blank", "about:blank", True),
    ("about:*", "about:version", True),
    ("data:*", "data:monkey", True),
    ("javascript:*", "javascript:atemyhomework", True),
    ("data:*", "about:blank", False),
])
def test_special_schemes(pattern, url, expected):
    assert urlmatch.UrlPattern(pattern).matches(QUrl(url)) == expected


class TestFileScheme:

    @pytest.fixture(params=[
        'file:///foo*',
        'file://foo*',
        # FIXME This doesn't pass all tests
        pytest.param('file://localhost/foo*', marks=pytest.mark.skip(
            reason="We're not handling this correctly in all cases"))
    ])
    def up(self, request):
        return urlmatch.UrlPattern(request.param)

    def test_attrs(self, up):
        assert up._scheme == 'file'
        assert up._host is None
        assert not up._match_subdomains
        assert not up._match_all
        assert up._path == '/foo*'

    @pytest.mark.parametrize('url, expected', [
        ("file://foo", False),
        ("file://foobar", False),
        ("file:///foo", True),
        ("file:///foobar", True),
        ("file://localhost/foo", True),
    ])
    def test_urls(self, up, url, expected):
        assert up.matches(QUrl(url)) == expected
