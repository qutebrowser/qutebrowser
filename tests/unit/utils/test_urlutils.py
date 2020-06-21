# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.utils.urlutils."""

import os.path
import logging

import attr
from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QNetworkProxy
import pytest

from qutebrowser.api import cmdutils
from qutebrowser.browser.network import pac
from qutebrowser.utils import utils, urlutils, usertypes
from helpers import utils as testutils


class FakeDNS:

    """Helper class for the fake_dns fixture.

    Class attributes:
        FakeDNSAnswer: Helper class imitating a QHostInfo object
                       (used by fromname_mock).

    Attributes:
        used: Whether the fake DNS server was used since it was
              created/reset.
        answer: What to return for the given host(True/False). Needs to be set
                when fromname_mock is called.
    """

    @attr.s
    class FakeDNSAnswer:

        error = attr.ib()

    def __init__(self):
        self.used = False
        self.answer = None

    def __repr__(self):
        return utils.get_repr(self, used=self.used, answer=self.answer)

    def reset(self):
        """Reset used/answer as if the FakeDNS was freshly created."""
        self.used = False
        self.answer = None

    def _get_error(self):
        return not self.answer

    def fromname_mock(self, _host):
        """Simple mock for QHostInfo::fromName returning a FakeDNSAnswer."""
        if self.answer is None:
            raise ValueError("Got called without answer being set. This means "
                             "something tried to make an unexpected DNS "
                             "request (QHostInfo::fromName).")
        if self.used:
            raise ValueError("Got used twice!.")
        self.used = True
        return self.FakeDNSAnswer(error=self._get_error)


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    """Patched QHostInfo.fromName to catch DNS requests.

    With autouse=True so accidental DNS requests get discovered because the
    fromname_mock will be called without answer being set.
    """
    dns = FakeDNS()
    monkeypatch.setattr(urlutils.QHostInfo, 'fromName', dns.fromname_mock)
    return dns


@pytest.fixture(autouse=True)
def init_config(config_stub):
    config_stub.val.url.searchengines = {
        'test': 'http://www.qutebrowser.org/?q={}',
        'test-with-dash': 'http://www.example.org/?q={}',
        'path-search': 'http://www.example.org/{}',
        'quoted-path': 'http://www.example.org/{quoted}',
        'unquoted': 'http://www.example.org/?{unquoted}',
        'DEFAULT': 'http://www.example.com/?q={}',
    }


class TestFuzzyUrl:

    """Tests for urlutils.fuzzy_url()."""

    @pytest.fixture
    def os_mock(self, mocker):
        """Mock the os module and some os.path functions."""
        m = mocker.patch('qutebrowser.utils.urlutils.os')
        # Using / to get the same behavior across OS'
        m.path.join.side_effect = lambda *args: '/'.join(args)
        m.path.expanduser.side_effect = os.path.expanduser
        return m

    @pytest.fixture
    def is_url_mock(self, mocker):
        return mocker.patch('qutebrowser.utils.urlutils.is_url')

    @pytest.fixture
    def get_search_url_mock(self, mocker):
        return mocker.patch('qutebrowser.utils.urlutils._get_search_url')

    def test_file_relative_cwd(self, os_mock):
        """Test with relative=True, cwd set, and an existing file."""
        os_mock.path.exists.return_value = True
        os_mock.path.isabs.return_value = False

        url = urlutils.fuzzy_url('foo', cwd='cwd', relative=True)

        os_mock.path.exists.assert_called_once_with('cwd/foo')
        assert url == QUrl('file:cwd/foo')

    def test_file_relative(self, os_mock):
        """Test with relative=True and cwd unset."""
        os_mock.path.exists.return_value = True
        os_mock.path.abspath.return_value = 'abs_path'
        os_mock.path.isabs.return_value = False

        url = urlutils.fuzzy_url('foo', relative=True)

        os_mock.path.exists.assert_called_once_with('abs_path')
        assert url == QUrl('file:abs_path')

    def test_file_relative_os_error(self, os_mock, is_url_mock):
        """Test with relative=True, cwd unset and abspath raising OSError."""
        os_mock.path.abspath.side_effect = OSError
        os_mock.path.exists.return_value = True
        os_mock.path.isabs.return_value = False
        is_url_mock.return_value = True

        url = urlutils.fuzzy_url('foo', relative=True)
        assert not os_mock.path.exists.called
        assert url == QUrl('http://foo')

    @pytest.mark.parametrize('path, expected', [
        ('/foo', QUrl('file:///foo')),
        ('/bar\n', QUrl('file:///bar')),
    ])
    def test_file_absolute(self, path, expected, os_mock):
        """Test with an absolute path."""
        os_mock.path.exists.return_value = True
        os_mock.path.isabs.return_value = True

        url = urlutils.fuzzy_url(path)
        assert url == expected

    @pytest.mark.posix
    def test_file_absolute_expanded(self, os_mock):
        """Make sure ~ gets expanded correctly."""
        os_mock.path.exists.return_value = True
        os_mock.path.isabs.return_value = True

        url = urlutils.fuzzy_url('~/foo')
        assert url == QUrl('file://' + os.path.expanduser('~/foo'))

    def test_address(self, os_mock, is_url_mock):
        """Test passing something with relative=False."""
        os_mock.path.isabs.return_value = False
        is_url_mock.return_value = True

        url = urlutils.fuzzy_url('foo')
        assert url == QUrl('http://foo')

    def test_search_term(self, os_mock, is_url_mock, get_search_url_mock):
        """Test passing something with do_search=True."""
        os_mock.path.isabs.return_value = False
        is_url_mock.return_value = False
        get_search_url_mock.return_value = QUrl('search_url')

        url = urlutils.fuzzy_url('foo', do_search=True)
        assert url == QUrl('search_url')

    def test_search_term_value_error(self, os_mock, is_url_mock,
                                     get_search_url_mock):
        """Test with do_search=True and ValueError in _get_search_url."""
        os_mock.path.isabs.return_value = False
        is_url_mock.return_value = False
        get_search_url_mock.side_effect = ValueError

        url = urlutils.fuzzy_url('foo', do_search=True)
        assert url == QUrl('http://foo')

    def test_no_do_search(self, is_url_mock):
        """Test with do_search = False."""
        is_url_mock.return_value = False

        url = urlutils.fuzzy_url('foo', do_search=False)
        assert url == QUrl('http://foo')

    @pytest.mark.parametrize('do_search', [True, False])
    def test_invalid_url(self, do_search, is_url_mock, monkeypatch,
                         caplog):
        """Test with an invalid URL."""
        is_url_mock.return_value = True
        monkeypatch.setattr(urlutils, 'qurl_from_user_input',
                            lambda url: QUrl())
        with pytest.raises(urlutils.InvalidUrlError):
            with caplog.at_level(logging.ERROR):
                urlutils.fuzzy_url('foo', do_search=do_search)

    @pytest.mark.parametrize('url', ['', ' '])
    def test_empty(self, url):
        with pytest.raises(urlutils.InvalidUrlError):
            urlutils.fuzzy_url(url, do_search=True)

    @pytest.mark.parametrize('urlstring', [
        'http://www.qutebrowser.org/',
        '/foo',
        'test'
    ])
    def test_force_search(self, urlstring, get_search_url_mock):
        """Test the force search option."""
        get_search_url_mock.return_value = QUrl('search_url')

        url = urlutils.fuzzy_url(urlstring, force_search=True)

        assert url == QUrl('search_url')

    @pytest.mark.parametrize('path, check_exists', [
        ('/foo', False),
        ('/bar', True),
    ])
    def test_get_path_existing(self, path, check_exists, os_mock, caplog):
        """Test with an absolute path."""
        os_mock.path.exists.return_value = False
        expected = None if check_exists else path

        url = urlutils.get_path_if_valid(path, check_exists=check_exists)
        assert url == expected

    def test_get_path_unicode_encode_error(self, os_mock, caplog):
        """Make sure LC_ALL=C is handled correctly."""
        err = UnicodeEncodeError('ascii', '', 0, 2, 'foo')
        os_mock.path.exists.side_effect = err

        url = urlutils.get_path_if_valid('/', check_exists=True)
        assert url is None

        msg = ("URL contains characters which are not present in the current "
               "locale")
        assert caplog.messages[-1] == msg


@pytest.mark.parametrize('url, special', [
    ('file:///tmp/foo', True),
    ('about:blank', True),
    ('qute:version', True),
    ('qute://version', True),
    ('http://www.qutebrowser.org/', False),
    ('www.qutebrowser.org', False),
])
def test_special_urls(url, special):
    assert urlutils.is_special_url(QUrl(url)) == special


@pytest.mark.parametrize('open_base_url', [True, False])
@pytest.mark.parametrize('url, host, query', [
    ('testfoo', 'www.example.com', 'q=testfoo'),
    ('test testfoo', 'www.qutebrowser.org', 'q=testfoo'),
    ('test testfoo bar foo', 'www.qutebrowser.org', 'q=testfoo bar foo'),
    ('test testfoo ', 'www.qutebrowser.org', 'q=testfoo'),
    ('!python testfoo', 'www.example.com', 'q=%21python testfoo'),
    ('blub testfoo', 'www.example.com', 'q=blub testfoo'),
    ('stripped ', 'www.example.com', 'q=stripped'),
    ('test-with-dash testfoo', 'www.example.org', 'q=testfoo'),
    ('test/with/slashes', 'www.example.com', 'q=test/with/slashes'),
    ('test path-search', 'www.qutebrowser.org', 'q=path-search'),
    ('slash/and&amp', 'www.example.com', 'q=slash/and%26amp'),
    ('unquoted one=1&two=2', 'www.example.org', 'one=1&two=2'),
])
def test_get_search_url(config_stub, url, host, query, open_base_url):
    """Test _get_search_url().

    Args:
        url: The "URL" to enter.
        host: The expected search machine host.
        query: The expected search query.
    """
    config_stub.val.url.open_base_url = open_base_url
    url = urlutils._get_search_url(url)
    assert url.host() == host
    assert url.query() == query


@pytest.mark.parametrize('open_base_url', [True, False])
@pytest.mark.parametrize('url, host, path', [
    ('path-search t/w/s', 'www.example.org', 't/w/s'),
    ('quoted-path t/w/s', 'www.example.org', 't%2Fw%2Fs'),
])
def test_get_search_url_for_path_search(config_stub, url, host, path, open_base_url):
    """Test _get_search_url_for_path_search().

    Args:
        url: The "URL" to enter.
        host: The expected search machine host.
        path: The expected path on that host that is requested.
    """
    config_stub.val.url.open_base_url = open_base_url
    url = urlutils._get_search_url(url)
    assert url.host() == host
    assert url.path(options=QUrl.PrettyDecoded) == '/' + path


@pytest.mark.parametrize('url, host', [
    ('test', 'www.qutebrowser.org'),
    ('test-with-dash', 'www.example.org'),
])
def test_get_search_url_open_base_url(config_stub, url, host):
    """Test _get_search_url() with url.open_base_url_enabled.

    Args:
        url: The "URL" to enter.
        host: The expected search machine host.
        query: The expected search query.
    """
    config_stub.val.url.open_base_url = True
    url = urlutils._get_search_url(url)
    assert not url.path()
    assert not url.fragment()
    assert not url.query()
    assert url.host() == host


@pytest.mark.parametrize('url', ['\n', ' ', '\n '])
def test_get_search_url_invalid(url):
    with pytest.raises(ValueError):
        urlutils._get_search_url(url)


@pytest.mark.parametrize('is_url, is_url_no_autosearch, uses_dns, url', [
    # Normal hosts
    (True, True, False, 'http://foobar'),
    (True, True, False, 'localhost:8080'),
    (True, True, True, 'qutebrowser.org'),
    (True, True, True, ' qutebrowser.org '),
    (True, True, False, 'http://user:password@example.com/foo?bar=baz#fish'),
    (True, True, True, 'existing-tld.domains'),
    # Internationalized domain names
    (True, True, True, '\u4E2D\u56FD.\u4E2D\u56FD'),  # Chinese TLD
    (True, True, True, 'xn--fiqs8s.xn--fiqs8s'),  # The same in punycode
    # Encoded space in explicit url
    (True, True, False, 'http://sharepoint/sites/it/IT%20Documentation/Forms/AllItems.aspx'),
    # IPs
    (True, True, False, '127.0.0.1'),
    (True, True, False, '::1'),
    (True, True, True, '2001:41d0:2:6c11::1'),
    (True, True, True, '[2001:41d0:2:6c11::1]:8000'),
    (True, True, True, '94.23.233.17'),
    (True, True, True, '94.23.233.17:8000'),
    # Special URLs
    (True, True, False, 'file:///tmp/foo'),
    (True, True, False, 'about:blank'),
    (True, True, False, 'qute:version'),
    (True, True, False, 'qute://version'),
    (True, True, False, 'localhost'),
    # _has_explicit_scheme False, special_url True
    (True, True, False, 'qute::foo'),
    (True, True, False, 'qute:://foo'),
    # Invalid URLs
    (False, False, False, ''),
    (False, True, False, 'onlyscheme:'),
    (False, True, False, 'http:foo:0'),
    # Not URLs
    (False, True, False, 'foo bar'),  # no DNS because of space
    (False, True, False, 'localhost test'),  # no DNS because of space
    (False, True, False, 'another . test'),  # no DNS because of space
    (False, True, True, 'foo'),
    (False, True, False, 'this is: not a URL'),  # no DNS because of space
    (False, True, False, 'foo user@host.tld'),  # no DNS because of space
    (False, True, False, '23.42'),  # no DNS because bogus-IP
    (False, True, False, '1337'),  # no DNS because bogus-IP
    (False, True, True, 'deadbeef'),
    (False, True, True, 'hello.'),
    (False, True, False, 'site:cookies.com oatmeal raisin'),
    (False, True, True, 'example.search_string'),
    (False, True, True, 'example_search.string'),
    # no DNS because there is no host
    (False, True, False, 'foo::bar'),
    # Valid search term with autosearch
    (False, False, False, 'test foo'),
    (False, False, False, 'test user@host.tld'),
    # autosearch = False
    (False, True, False, 'This is a URL without autosearch'),
])
@pytest.mark.parametrize('auto_search', ['dns', 'naive', 'never'])
def test_is_url(config_stub, fake_dns,
                is_url, is_url_no_autosearch, uses_dns, url, auto_search):
    """Test is_url().

    Args:
        is_url: Whether the given string is a URL with auto_search dns/naive.
        is_url_no_autosearch: Whether the given string is a URL with
                              auto_search false.
        uses_dns: Whether the given string should fire a DNS request for the
                  given URL.
        url: The URL to test, as a string.
        auto_search: With which auto_search setting to test
    """
    config_stub.val.url.auto_search = auto_search
    if auto_search == 'dns':
        if uses_dns:
            fake_dns.answer = True
            result = urlutils.is_url(url)
            assert fake_dns.used
            assert result
            fake_dns.reset()

            fake_dns.answer = False
            result = urlutils.is_url(url)
            assert fake_dns.used
            assert not result
        else:
            result = urlutils.is_url(url)
            assert not fake_dns.used
            assert result == is_url
    elif auto_search == 'naive':
        assert urlutils.is_url(url) == is_url
        assert not fake_dns.used
    elif auto_search == 'never':
        assert urlutils.is_url(url) == is_url_no_autosearch
        assert not fake_dns.used
    else:
        raise ValueError("Invalid value {!r} for auto_search!".format(
            auto_search))


@pytest.mark.parametrize('auto_search, open_base_url, is_url', [
    ('naive', True, False),
    ('naive', False, False),
    ('never', True, False),
    ('never', False, True),
])
def test_searchengine_is_url(config_stub, auto_search, open_base_url, is_url):
    config_stub.val.url.auto_search = auto_search
    config_stub.val.url.open_base_url = open_base_url
    assert urlutils.is_url('test') == is_url


@pytest.mark.parametrize('user_input, output', [
    ('qutebrowser.org', 'http://qutebrowser.org'),
    ('http://qutebrowser.org', 'http://qutebrowser.org'),
    ('::1/foo', 'http://[::1]/foo'),
    ('[::1]/foo', 'http://[::1]/foo'),
    ('http://[::1]', 'http://[::1]'),
    ('qutebrowser.org', 'http://qutebrowser.org'),
    ('http://qutebrowser.org', 'http://qutebrowser.org'),
    ('::1/foo', 'http://[::1]/foo'),
    ('[::1]/foo', 'http://[::1]/foo'),
    ('http://[::1]', 'http://[::1]'),
])
def test_qurl_from_user_input(user_input, output):
    """Test qurl_from_user_input.

    Args:
        user_input: The string to pass to qurl_from_user_input.
        output: The expected QUrl string.
    """
    url = urlutils.qurl_from_user_input(user_input)
    assert url.toString() == output


@pytest.mark.parametrize('url, valid, has_err_string', [
    ('http://www.example.com/', True, False),
    ('', False, False),
    ('://', False, True),
])
def test_invalid_url_error(message_mock, caplog, url, valid, has_err_string):
    """Test invalid_url_error().

    Args:
        url: The URL to check.
        valid: Whether the QUrl is valid (isValid() == True).
        has_err_string: Whether the QUrl is expected to have errorString set.
    """
    qurl = QUrl(url)
    assert qurl.isValid() == valid
    if valid:
        with pytest.raises(ValueError):
            urlutils.invalid_url_error(qurl, '')
        assert not message_mock.messages
    else:
        assert bool(qurl.errorString()) == has_err_string
        with caplog.at_level(logging.ERROR):
            urlutils.invalid_url_error(qurl, 'frozzle')

        msg = message_mock.getmsg(usertypes.MessageLevel.error)
        if has_err_string:
            expected_text = ("Trying to frozzle with invalid URL - " +
                             qurl.errorString())
        else:
            expected_text = "Trying to frozzle with invalid URL"
        assert msg.text == expected_text


@pytest.mark.parametrize('url, valid, has_err_string', [
    ('http://www.example.com/', True, False),
    ('', False, False),
    ('://', False, True),
])
def test_raise_cmdexc_if_invalid(url, valid, has_err_string):
    """Test raise_cmdexc_if_invalid.

    Args:
        url: The URL to check.
        valid: Whether the QUrl is valid (isValid() == True).
        has_err_string: Whether the QUrl is expected to have errorString set.
    """
    qurl = QUrl(url)
    assert qurl.isValid() == valid
    if valid:
        urlutils.raise_cmdexc_if_invalid(qurl)
    else:
        assert bool(qurl.errorString()) == has_err_string
        if has_err_string:
            expected_text = "Invalid URL - " + qurl.errorString()
        else:
            expected_text = "Invalid URL"
        with pytest.raises(cmdutils.CommandError, match=expected_text):
            urlutils.raise_cmdexc_if_invalid(qurl)


@pytest.mark.parametrize('qurl, output', [
    (QUrl(), None),
    (QUrl('http://qutebrowser.org/test.html'), 'test.html'),
    (QUrl('http://qutebrowser.org/foo.html#bar'), 'foo.html'),
    (QUrl('http://user:password@qutebrowser.org/foo?bar=baz#fish'), 'foo'),
    (QUrl('http://qutebrowser.org/'), 'qutebrowser.org.html'),
    (QUrl('qute://'), None),
])
def test_filename_from_url(qurl, output):
    assert urlutils.filename_from_url(qurl) == output


@pytest.mark.parametrize('qurl, expected', [
    (QUrl('ftp://example.com/'), ('ftp', 'example.com', 21)),
    (QUrl('ftp://example.com:2121/'), ('ftp', 'example.com', 2121)),
    (QUrl('http://qutebrowser.org:8010/waterfall'),
     ('http', 'qutebrowser.org', 8010)),
    (QUrl('https://example.com/'), ('https', 'example.com', 443)),
    (QUrl('https://example.com:4343/'), ('https', 'example.com', 4343)),
    (QUrl('http://user:password@qutebrowser.org/foo?bar=baz#fish'),
     ('http', 'qutebrowser.org', 80)),
])
def test_host_tuple_valid(qurl, expected):
    assert urlutils.host_tuple(qurl) == expected


@pytest.mark.parametrize('qurl, expected', [
    (QUrl(), urlutils.InvalidUrlError),
    (QUrl('qute://'), ValueError),
    (QUrl('qute://foobar'), ValueError),
    (QUrl('mailto:nobody'), ValueError),
])
def test_host_tuple_invalid(qurl, expected):
    with pytest.raises(expected):
        urlutils.host_tuple(qurl)


class TestInvalidUrlError:

    @pytest.mark.parametrize('url, raising, has_err_string', [
        (QUrl(), False, False),
        (QUrl('http://www.example.com/'), True, False),
        (QUrl('://'), False, True),
    ])
    def test_invalid_url_error(self, url, raising, has_err_string):
        """Test InvalidUrlError.

        Args:
            url: The URL to pass to InvalidUrlError.
            raising; True if the InvalidUrlError should raise itself.
            has_err_string: Whether the QUrl is expected to have errorString
                            set.
        """
        if raising:
            expected_exc = ValueError
        else:
            expected_exc = urlutils.InvalidUrlError

        with pytest.raises(expected_exc) as excinfo:
            raise urlutils.InvalidUrlError(url)

        if not raising:
            expected_text = "Invalid URL"
            if has_err_string:
                expected_text += " - " + url.errorString()
            assert str(excinfo.value) == expected_text


@pytest.mark.parametrize('are_same, url1, url2', [
    (True, 'http://example.com', 'http://www.example.com'),
    (True, 'http://bbc.co.uk', 'https://www.bbc.co.uk'),
    (True, 'http://many.levels.of.domains.example.com', 'http://www.example.com'),
    (True, 'http://idn.иком.museum', 'http://idn2.иком.museum'),
    (True, 'http://one.not_a_valid_tld', 'http://one.not_a_valid_tld'),

    (False, 'http://bbc.co.uk', 'http://example.co.uk'),
    (False, 'https://example.kids.museum', 'http://example.kunst.museum'),
    (False, 'http://idn.иком.museum', 'http://idn.ירושלים.museum'),
    (False, 'http://one.not_a_valid_tld', 'http://two.not_a_valid_tld'),
])
def test_same_domain(are_same, url1, url2):
    """Test same_domain."""
    assert urlutils.same_domain(QUrl(url1), QUrl(url2)) == are_same
    assert urlutils.same_domain(QUrl(url2), QUrl(url1)) == are_same


@pytest.mark.parametrize('url1, url2', [
    ('http://example.com', ''),
    ('', 'http://example.com'),
])
def test_same_domain_invalid_url(url1, url2):
    """Test same_domain with invalid URLs."""
    with pytest.raises(urlutils.InvalidUrlError):
        urlutils.same_domain(QUrl(url1), QUrl(url2))


@pytest.mark.parametrize('url, expected', [
    ('http://example.com', 'http://example.com'),
    ('http://ünicode.com', 'http://xn--nicode-2ya.com'),
    ('http://foo.bar/?header=text/pläin',
     'http://foo.bar/?header=text/pl%C3%A4in'),
])
def test_encoded_url(url, expected):
    url = QUrl(url)
    assert urlutils.encoded_url(url) == expected


def test_file_url():
    assert urlutils.file_url('/foo/bar') == 'file:///foo/bar'


def test_data_url():
    url = urlutils.data_url('text/plain', b'foo')
    assert url == QUrl('data:text/plain;base64,Zm9v')


@pytest.mark.parametrize('url, expected', [
    # No IDN
    (QUrl('http://www.example.com'), 'http://www.example.com'),
    # IDN in domain
    (QUrl('http://www.ä.com'), '(www.xn--4ca.com) http://www.ä.com'),
    # IDN with non-whitelisted TLD
    (QUrl('http://www.ä.foo'), 'http://www.xn--4ca.foo'),
    # Unicode only in path
    (QUrl('http://www.example.com/ä'), 'http://www.example.com/ä'),
    # Unicode only in TLD (looks like Qt shows Punycode with рф...)
    (QUrl('http://www.example.xn--p1ai'),
     '(www.example.xn--p1ai) http://www.example.рф'),
    # https://bugreports.qt.io/browse/QTBUG-60364
    pytest.param(QUrl('http://www.xn--80ak6aa92e.com'),
                 '(unparseable URL!) http://www.аррӏе.com',
                 marks=testutils.qt58),
    pytest.param(QUrl('http://www.xn--80ak6aa92e.com'),
                 'http://www.xn--80ak6aa92e.com',
                 marks=testutils.qt59),
])
def test_safe_display_string(url, expected):
    assert urlutils.safe_display_string(url) == expected


def test_safe_display_string_invalid():
    with pytest.raises(urlutils.InvalidUrlError):
        urlutils.safe_display_string(QUrl())


def test_query_string():
    url = QUrl('https://www.example.com/?foo=bar')
    assert urlutils.query_string(url) == 'foo=bar'


class TestProxyFromUrl:

    @pytest.mark.parametrize('url, expected', [
        ('socks://example.com/',
         QNetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com')),
        ('socks5://example.com',
         QNetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com')),
        ('socks5://example.com:2342',
         QNetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 2342)),
        ('socks5://foo@example.com',
         QNetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 0, 'foo')),
        ('socks5://foo:bar@example.com',
         QNetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 0, 'foo',
                       'bar')),
        ('socks5://foo:bar@example.com:2323',
         QNetworkProxy(QNetworkProxy.Socks5Proxy, 'example.com', 2323,
                       'foo', 'bar')),
        ('direct://', QNetworkProxy(QNetworkProxy.NoProxy)),
    ])
    def test_proxy_from_url_valid(self, url, expected):
        assert urlutils.proxy_from_url(QUrl(url)) == expected

    @pytest.mark.qt_log_ignore(
        r'^QHttpNetworkConnectionPrivate::_q_hostLookupFinished could not '
        r'de-queue request, failed to report HostNotFoundError')
    @pytest.mark.parametrize('scheme', ['pac+http', 'pac+https'])
    def test_proxy_from_url_pac(self, scheme, qapp):
        fetcher = urlutils.proxy_from_url(QUrl('{}://foo'.format(scheme)))
        assert isinstance(fetcher, pac.PACFetcher)

    @pytest.mark.parametrize('url, exception', [
        ('blah', urlutils.InvalidProxyTypeError),
        (':', urlutils.InvalidUrlError),  # invalid URL
        # Invalid/unsupported scheme
        ('ftp://example.com/', urlutils.InvalidProxyTypeError),
        ('socks4://example.com/', urlutils.InvalidProxyTypeError),
    ])
    def test_invalid(self, url, exception):
        with pytest.raises(exception):
            urlutils.proxy_from_url(QUrl(url))
