# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.utils.urlmatch.

The tests are mostly inspired by Chromium's:
https://cs.chromium.org/chromium/src/extensions/common/url_pattern_unittest.cc

Currently not tested:
- Nested filesystem:// URLs as we don't have those.
- Unicode matching because QUrl doesn't like those URLs.
- Any other features we don't need, such as .GetAsString() or set operations.
"""

import string

import pytest
import hypothesis
import hypothesis.strategies as hst
from PyQt5.QtCore import QUrl

from qutebrowser.utils import urlmatch


@pytest.mark.parametrize('pattern, error', [
    ### Chromium: kMissingSchemeSeparator
    ## TEST(ExtensionURLPatternTest, ParseInvalid)
    # ("http", "No scheme given"),
    ("http:", "Invalid port: Port is empty"),
    ("http:/", "Invalid port: Port is empty"),
    ("about://", "Pattern without path"),
    ("http:/bar", "Invalid port: Port is empty"),

    ### Chromium: kEmptyHost
    ## TEST(ExtensionURLPatternTest, ParseInvalid)
    ("http://", "Pattern without host"),
    ("http:///", "Pattern without host"),
    ("http://:1234/", "Pattern without host"),
    ("http://*./", "Pattern without host"),
    ## TEST(ExtensionURLPatternTest, IPv6Patterns)
    ("http://[]:8888/*", "Pattern without host"),

    ### Chromium: kEmptyPath
    ## TEST(ExtensionURLPatternTest, ParseInvalid)
    # We deviate from Chromium and allow this for ease of use
    # ("http://bar", "..."),

    ### Chromium: kInvalidHost
    ## TEST(ExtensionURLPatternTest, ParseInvalid)
    ("http://\0www/", "May not contain NUL byte"),
    ## TEST(ExtensionURLPatternTest, IPv6Patterns)
    # No closing bracket (`]`).
    ("http://[2607:f8b0:4005:805::200e/*", "Invalid IPv6 URL"),
    # Two closing brackets (`]]`).
    pytest.param("http://[2607:f8b0:4005:805::200e]]/*", "Invalid IPv6 URL", marks=pytest.mark.xfail(reason="https://bugs.python.org/issue34360")),
    # Two open brackets (`[[`).
    ("http://[[2607:f8b0:4005:805::200e]/*", r"""Expected '\]' to match '\[' in hostname; source was "\[2607:f8b0:4005:805::200e"; host = """""),
    # Too few colons in the last chunk.
    ("http://[2607:f8b0:4005:805:200e]/*", 'Invalid IPv6 address; source was "2607:f8b0:4005:805:200e"; host = ""'),
    # Non-hex piece.
    ("http://[2607:f8b0:4005:805:200e:12:bogus]/*", 'Invalid IPv6 address; source was "2607:f8b0:4005:805:200e:12:bogus"; host = ""'),

    ### Chromium: kInvalidHostWildcard
    ## TEST(ExtensionURLPatternTest, ParseInvalid)
    ("http://*foo/bar", "Invalid host wildcard"),
    ("http://foo.*.bar/baz", "Invalid host wildcard"),
    ("http://fo.*.ba:123/baz", "Invalid host wildcard"),
    ("http://foo.*/bar", "Invalid host wildcard"),

    ### Chromium: kInvalidPort
    ## TEST(ExtensionURLPatternTest, Ports)
    ("http://foo:/", "Invalid port: Port is empty"),
    ("http://*.foo:/", "Invalid port: Port is empty"),
    ("http://foo:com/", "Invalid port: .* 'com'"),
    ("http://foo:123456/", "Invalid port: Port out of range 0-65535"),
    ("http://foo:80:80/monkey", "Invalid port: .* '80:80'"),
    ("chrome://foo:1234/bar", "Ports are unsupported with chrome scheme"),
    # No port specified, but port separator.
    ("http://[2607:f8b0:4005:805::200e]:/*", "Invalid port: Port is empty"),

    ### Additional tests
    ("http://[", "Invalid IPv6 URL"),
    ("http://[fc2e::bb88::edac]", 'Invalid IPv6 address; source was "fc2e::bb88::edac"; host = ""'),
    ("http://[fc2e:0e35:bb88::edac:fc2e:0e35:bb88:edac]", 'Invalid IPv6 address; source was "fc2e:0e35:bb88::edac:fc2e:0e35:bb88:edac"; host = ""'),
    ("http://[fc2e:0e35:bb88:af:edac:fc2e:0e35:bb88:edac]", 'Invalid IPv6 address; source was "fc2e:0e35:bb88:af:edac:fc2e:0e35:bb88:edac"; host = ""'),
    ("http://[127.0.0.1:fc2e::bb88:edac]", r'Invalid IPv6 address; source was "127\.0\.0\.1:fc2e::bb88:edac'),
    ("http://[fc2e::bb88", "Invalid IPv6 URL"),
    ("http://[fc2e:bb88:edac]", 'Invalid IPv6 address; source was "fc2e:bb88:edac"; host = ""'),
    ("http://[fc2e:bb88:edac::z]", 'Invalid IPv6 address; source was "fc2e:bb88:edac::z"; host = ""'),
    ("http://[fc2e:bb88:edac::2]:2a2", "Invalid port: .* '2a2'"),
    ("://", "Missing scheme"),
])
def test_invalid_patterns(pattern, error):
    with pytest.raises(urlmatch.ParseError, match=error):
        urlmatch.UrlPattern(pattern)


@pytest.mark.parametrize('host', ['.', ' ', ' .', '. ', '. .', '. . .', ' . '])
def test_whitespace_hosts(host):
    """Test that whitespace dot hosts are invalid.

    This is a deviation from Chromium.
    """
    template = 'https://{}/*'
    url = QUrl(template.format(host))
    assert not url.isValid()

    with pytest.raises(urlmatch.ParseError,
                       match='Invalid host|Pattern without host'):
        urlmatch.UrlPattern(template.format(host))


@pytest.mark.parametrize('pattern, port', [
    ## TEST(ExtensionURLPatternTest, Ports)
    ("http://foo:1234/", 1234),
    ("http://foo:1234/bar", 1234),
    ("http://*.foo:1234/", 1234),
    ("http://*.foo:1234/bar", 1234),
    ("http://*:1234/", 1234),
    ("http://*:*/", None),
    ("http://foo:*/", None),
    ("file://foo:1234/bar", None),
    # Port-like strings in the path should not trigger a warning.
    ("http://*/:1234", None),
    ("http://*.foo/bar:1234", None),
    ("http://foo/bar:1234/path", None),
])
def test_port(pattern, port):
    up = urlmatch.UrlPattern(pattern)
    assert up._port == port


@pytest.mark.parametrize('pattern, path', [
    ("http://foo/", '/'),
    ("http://foo/*", None),
])
def test_parse_path(pattern, path):
    up = urlmatch.UrlPattern(pattern)
    assert up._path == path


@pytest.mark.parametrize('pattern, scheme, host, path', [
    ("http://example.com", 'http', 'example.com', None),  # no path
    ("example.com/path", None, 'example.com', '/path'),  # no scheme
    ("example.com", None, 'example.com', None),  # no scheme and no path
    ("example.com:1234", None, 'example.com', None),  # no scheme/path but port
    ("data:monkey", 'data', None, 'monkey'),  # existing scheme
])
def test_lightweight_patterns(pattern, scheme, host, path):
    """Make sure we can leave off parts of a URL.

    This is a deviation from Chromium to make patterns more user-friendly.
    """
    up = urlmatch.UrlPattern(pattern)
    assert up._scheme == scheme
    assert up.host == host
    assert up._path == path


class TestMatchAllPagesForGivenScheme:

    """Based on TEST(ExtensionURLPatternTest, Match1)."""

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern("http://*/*")

    def test_attrs(self, up):
        assert up._scheme == 'http'
        assert up.host is None
        assert up._match_subdomains
        assert not up._match_all
        assert up._path is None

    @pytest.mark.parametrize('url, expected', [
        ("http://google.com", True),
        ("http://yahoo.com", True),
        ("http://google.com/foo", True),
        ("https://google.com", False),
        ("http://74.125.127.100/search", True),
        # Additional tests
        ("http://google.com:80", True),
        ("http://google.com.", True),
        ("http://[fc2e:0e35:bb88::edac]", True),
        ("http://[fc2e:e35:bb88::edac]", True),
        ("http://[fc2e:e35:bb88::127.0.0.1]", True),
        ("http://[::1]/bar", True),
    ])
    def test_urls(self, up, url, expected):
        assert up.matches(QUrl(url)) == expected


class TestMatchAllDomains:

    """Based on TEST(ExtensionURLPatternTest, Match2)."""

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern("https://*/foo*")

    def test_attrs(self, up):
        assert up._scheme == 'https'
        assert up.host is None
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

    """Based on TEST(ExtensionURLPatternTest, Match3)."""

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern("http://*.google.com/foo*bar")

    def test_attrs(self, up):
        assert up._scheme == 'http'
        assert up.host == 'google.com'
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

    """Based on TEST(ExtensionURLPatternTest, Match5)."""

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern(r"file:///foo-bar\*baz")

    def test_attrs(self, up):
        assert up._scheme == 'file'
        assert up.host is None
        assert not up._match_subdomains
        assert not up._match_all
        assert up._path == r'/foo-bar\*baz'

    @pytest.mark.parametrize('url, expected', [
        ## TEST(ExtensionURLPatternTest, Match5)
        # We use - instead of ? so it doesn't get treated as query
        (r"file:///foo-bar\hellobaz", True),
        (r"file:///fooXbar\hellobaz", False),
    ])
    def test_urls(self, up, url, expected):
        assert up.matches(QUrl(url)) == expected


class TestMatchIpAddresses:

    """Based on TEST(ExtensionURLPatternTest, Match6/7)."""

    @pytest.mark.parametrize('pattern, host, match_subdomains', [
        ("http://127.0.0.1/*", "127.0.0.1", False),
        ("http://*.0.0.1/*", "0.0.1", True),
        ## Others
        ("http://[::1]/*", "::1", False),
        ("http://[0::1]/*", "::1", False),
        ("http://[::01]/*", "::1", False),
        ("http://[0:0:0:0:20::1]/*", "::20:0:0:1", False),
    ])
    def test_attrs(self, pattern, host, match_subdomains):
        up = urlmatch.UrlPattern(pattern)
        assert up._scheme == 'http'
        assert up.host == host
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


## FIXME Missing TEST(ExtensionURLPatternTest, Match8) (unicode)?


class TestMatchChromeUrls:

    """Based on TEST(ExtensionURLPatternTest, Match9/10)."""

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern("chrome://favicon/*")

    def test_attrs(self, up):
        assert up._scheme == 'chrome'
        assert up.host == 'favicon'
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

    """Based on TEST(ExtensionURLPatternTest, Match10/11)."""

    @pytest.fixture(params=['*://*/*', '*://*:*/*', '<all_urls>', '*://*'])
    def up(self, request):
        return urlmatch.UrlPattern(request.param)

    def test_attrs_common(self, up):
        assert up._scheme is None
        assert up.host is None
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
        "javascript:",
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
    """Based on TEST(ExtensionURLPatternTest, Match13)."""
    assert urlmatch.UrlPattern(pattern).matches(QUrl(url)) == expected


class TestFileScheme:

    """Based on TEST(ExtensionURLPatternTest, Match14/15/16)."""

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
        assert up.host is None
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


class TestMatchSpecificPort:

    """Based on TEST(ExtensionURLPatternTest, Match17)."""

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern("http://www.example.com:80/foo")

    def test_attrs(self, up):
        assert up._scheme == 'http'
        assert up.host == 'www.example.com'
        assert not up._match_subdomains
        assert not up._match_all
        assert up._path == '/foo'
        assert up._port == 80

    @pytest.mark.parametrize('url, expected', [
        ("http://www.example.com:80/foo", True),
        ("http://www.example.com/foo", True),
        ("http://www.example.com:8080/foo", False),
    ])
    def test_urls(self, up, url, expected):
        assert up.matches(QUrl(url)) == expected


class TestExplicitPortWildcard:

    """Based on TEST(ExtensionURLPatternTest, Match18)."""

    @pytest.fixture
    def up(self):
        return urlmatch.UrlPattern("http://www.example.com:*/foo")

    def test_attrs(self, up):
        assert up._scheme == 'http'
        assert up.host == 'www.example.com'
        assert not up._match_subdomains
        assert not up._match_all
        assert up._path == '/foo'
        assert up._port is None

    @pytest.mark.parametrize('url, expected', [
        ("http://www.example.com:80/foo", True),
        ("http://www.example.com/foo", True),
        ("http://www.example.com:8080/foo", True),
    ])
    def test_urls(self, up, url, expected):
        assert up.matches(QUrl(url)) == expected


def test_ignore_missing_slashes():
    """Based on TEST(ExtensionURLPatternTest, IgnoreMissingBackslashes)."""
    pattern1 = urlmatch.UrlPattern("http://www.example.com/example")
    pattern2 = urlmatch.UrlPattern("http://www.example.com/example/*")
    url1 = QUrl('http://www.example.com/example')
    url2 = QUrl('http://www.example.com/example/')

    # Same patterns should match same URLs.
    assert pattern1.matches(url1)
    assert pattern2.matches(url1)
    # The not terminated path should match the terminated pattern.
    assert pattern2.matches(url1)
    # The terminated path however should not match the unterminated pattern.
    assert not pattern1.matches(url2)


def test_trailing_slash():
    """Contrary to Chromium, we allow to leave off a trailing slash."""
    url = QUrl('http://www.example.com/')
    pattern = urlmatch.UrlPattern('http://www.example.com')
    assert pattern.matches(url)


@pytest.mark.parametrize('pattern', ['*://example.com/*',
                                     '*://example.com./*'])
@pytest.mark.parametrize('url', ['http://example.com/',
                                 'http://example.com./'])
def test_trailing_dot_domain(pattern, url):
    """Both patterns should match trailing dot and non trailing dot domains.

    More information about this not obvious behavior can be found in [1].

    RFC 1738 [2] specifies clearly that the <host> part of a URL is supposed to
    contain a fully qualified domain name:

    3.1. Common Internet Scheme Syntax
         //<user>:<password>@<host>:<port>/<url-path>

     host
         The fully qualified domain name of a network host

    [1] http://www.dns-sd.org./TrailingDotsInDomainNames.html
    [2] http://www.ietf.org/rfc/rfc1738.txt
    """
    assert urlmatch.UrlPattern(pattern).matches(QUrl(url))


class TestUncanonicalizedUrl:

    """Test that URLPattern properly canonicalizes uncanonicalized hosts.

    Equivalent to Chromium's TEST(ExtensionURLPatternTest, UncanonicalizedUrl).
    """

    @pytest.mark.parametrize('url', [
        'https://google.com',
        'https://maps.google.com',
    ])
    def test_lowercase(self, url):
        """Simple case: canonicalization should lowercase the host.

        This is important, since gOoGle.com would never be matched in
        practice.
        """
        pattern = urlmatch.UrlPattern('*://*.gOoGle.com/*')
        assert pattern.matches(QUrl(url))

    @pytest.mark.parametrize('url', [
        'https://ɡoogle.com',
        'https://xn--oogle-qmc.com/',
    ])
    def test_punycode(self, url):
        """Trickier case: internationalization with UTF8 characters.

        The first 'g' isn't actually a 'g'.
        """
        pattern = urlmatch.UrlPattern('https://*.ɡoogle.com/*')
        assert pattern.matches(QUrl(url))

    @pytest.mark.xfail(reason="Gets accepted by urllib.parse")
    def test_failing_canonicalization(self):
        """Sometimes, canonicalization can fail.

        Such as here, where we have invalid unicode characters. In that case,
        URLPattern parsing should also fail.

        This fails in Chromium, but Python's urllib.parse.urlparse happily
        tries to parse it...
        """
        with pytest.raises(urlmatch.ParseError):
            urlmatch.UrlPattern('https://\xef\xb7\x90zyx.com/*')

    @pytest.mark.xfail(reason="We return the original string")
    @pytest.mark.parametrize('pattern_str, string, host', [
        ('*://*.gOoGle.com/*',
         '*://*.google.com/*',
         'google.com'),
        ('https://*.ɡoogle.com/*',
         'https://*.xn--oogle-qmc.com/*',
         'xn--oogle-qmc.com'),
    ])
    def test_str(self, pattern_str, string, host):
        """Test that str() and .host get the canonicalized string.

        Contrary to Chromium, we return the original values here.
        """
        pattern = urlmatch.UrlPattern(pattern_str)
        assert str(pattern) == string
        assert pattern.host == host


def test_urlpattern_benchmark(benchmark):
    url = QUrl('https://www.example.com/barfoobar')

    def run():
        up = urlmatch.UrlPattern('https://*.example.com/*foo*')
        up.matches(url)

    benchmark(run)


URL_TEXT = hst.text(alphabet=string.ascii_letters)


@hypothesis.given(pattern=hst.builds(
    lambda *a: ''.join(a),
    # Scheme
    hst.sampled_from(['*', 'http', 'file']),
    # Separator
    hst.sampled_from([':', '://']),
    # Host
    hst.one_of(hst.just('*'),
               hst.builds(lambda *a: ''.join(a), hst.just('*.'), URL_TEXT),
               URL_TEXT),
    # Port
    hst.one_of(hst.just(''),
               hst.builds(lambda *a: ''.join(a), hst.just(':'),
                          hst.integers(min_value=0,
                                       max_value=65535).map(str))),
    # Path
    hst.one_of(hst.just(''),
               hst.builds(lambda *a: ''.join(a), hst.just('/'), URL_TEXT))
))
def test_urlpattern_hypothesis(pattern):
    try:
        up = urlmatch.UrlPattern(pattern)
    except urlmatch.ParseError:
        return
    up.matches(QUrl('https://www.example.com/'))


@pytest.mark.parametrize('text1, text2, equal', [
    # schemes
    ("http://en.google.com/blah/*/foo",
     "https://en.google.com/blah/*/foo",
     False),
    ("https://en.google.com/blah/*/foo",
     "https://en.google.com/blah/*/foo",
     True),
    ("https://en.google.com/blah/*/foo",
     "ftp://en.google.com/blah/*/foo",
     False),

    # subdomains
    ("https://en.google.com/blah/*/foo",
     "https://fr.google.com/blah/*/foo",
     False),
    ("https://www.google.com/blah/*/foo",
     "https://*.google.com/blah/*/foo",
     False),
    ("https://*.google.com/blah/*/foo",
     "https://*.google.com/blah/*/foo",
     True),

    # domains
    ("http://en.example.com/blah/*/foo",
     "http://en.google.com/blah/*/foo",
     False),

    # ports
    ("http://en.google.com:8000/blah/*/foo",
     "http://en.google.com/blah/*/foo",
     False),
    ("http://fr.google.com:8000/blah/*/foo",
     "http://fr.google.com:8000/blah/*/foo",
     True),
    ("http://en.google.com:8000/blah/*/foo",
     "http://en.google.com:8080/blah/*/foo",
     False),

    # paths
    ("http://en.google.com/blah/*/foo",
     "http://en.google.com/blah/*",
     False),
    ("http://en.google.com/*",
     "http://en.google.com/",
     False),
    ("http://en.google.com/*",
     "http://en.google.com/*",
     True),

    # all_urls
    ("<all_urls>",
     "<all_urls>",
     True),
    ("<all_urls>",
     "http://*/*",
     False)
])
def test_equal(text1, text2, equal):
    pat1 = urlmatch.UrlPattern(text1)
    pat2 = urlmatch.UrlPattern(text2)

    assert (pat1 == pat2) == equal
    assert (hash(pat1) == hash(pat2)) == equal


def test_equal_string():
    assert urlmatch.UrlPattern("<all_urls>") != '<all_urls>'


def test_repr():
    pat = urlmatch.UrlPattern('https://www.example.com/')
    expected = ("qutebrowser.utils.urlmatch.UrlPattern("
                "pattern='https://www.example.com/')")
    assert repr(pat) == expected


def test_str():
    text = 'https://www.example.com/'
    pat = urlmatch.UrlPattern(text)
    assert str(pat) == text
