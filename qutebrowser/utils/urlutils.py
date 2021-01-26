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

"""Utils regarding URL handling."""

import re
import base64
import os.path
import ipaddress
import posixpath
import urllib.parse
import mimetypes
from typing import Optional, Tuple, Union

from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QHostInfo, QHostAddress, QNetworkProxy

from qutebrowser.api import cmdutils
from qutebrowser.config import config
from qutebrowser.utils import log, qtutils, message, utils
from qutebrowser.browser.network import pac


# FIXME: we probably could raise some exceptions on invalid URLs
# https://github.com/qutebrowser/qutebrowser/issues/108


# URL schemes supported by QtWebEngine
WEBENGINE_SCHEMES = [
    'about',
    'data',
    'file',
    'filesystem',
    'ftp',
    'http',
    'https',
    'javascript',
    'ws',
    'wss',
]


class Error(Exception):

    """Base class for errors in this module."""


class InvalidUrlError(Error):

    """Error raised if a function got an invalid URL."""

    def __init__(self, url: QUrl) -> None:
        if url.isValid():
            raise ValueError("Got valid URL {}!".format(url.toDisplayString()))
        self.url = url
        self.msg = get_errstring(url)
        super().__init__(self.msg)


def _parse_search_term(s: str) -> Tuple[Optional[str], Optional[str]]:
    """Get a search engine name and search term from a string.

    Args:
        s: The string to get a search engine for.

    Return:
        A (engine, term) tuple, where engine is None for the default engine.
    """
    s = s.strip()
    split = s.split(maxsplit=1)
    if not split:
        raise ValueError("Empty search term!")

    if len(split) == 2:
        if split[0] in config.val.url.searchengines:
            engine: Optional[str] = split[0]
            term: Optional[str] = split[1]
        else:
            engine = None
            term = s
    else:
        if config.val.url.open_base_url and s in config.val.url.searchengines:
            engine = s
            term = None
        else:
            engine = None
            term = s

    log.url.debug("engine {}, term {!r}".format(engine, term))
    return (engine, term)


def _get_search_url(txt: str) -> QUrl:
    """Get a search engine URL for a text.

    Args:
        txt: Text to search for.

    Return:
        The search URL as a QUrl.
    """
    log.url.debug("Finding search engine for {!r}".format(txt))
    engine, term = _parse_search_term(txt)
    if not engine:
        engine = 'DEFAULT'
    if term:
        template = config.val.url.searchengines[engine]
        semiquoted_term = urllib.parse.quote(term)
        quoted_term = urllib.parse.quote(term, safe='')
        evaluated = template.format(semiquoted_term,
                                    unquoted=term,
                                    quoted=quoted_term,
                                    semiquoted=semiquoted_term)
        url = QUrl.fromUserInput(evaluated)
    else:
        url = QUrl.fromUserInput(config.val.url.searchengines[engine])
        url.setPath(None)  # type: ignore[arg-type]
        url.setFragment(None)  # type: ignore[arg-type]
        url.setQuery(None)  # type: ignore[call-overload]
    qtutils.ensure_valid(url)
    return url


def _is_url_naive(urlstr: str) -> bool:
    """Naive check if given URL is really a URL.

    Args:
        urlstr: The URL to check for, as string.

    Return:
        True if the URL really is a URL, False otherwise.
    """
    url = QUrl.fromUserInput(urlstr)
    assert url.isValid()
    host = url.host()

    # Valid IPv4/IPv6 address. Qt converts things like "23.42" or "1337" or
    # "0xDEAD" to IP addresses, which we don't like, so we check if the host
    # from Qt is part of the input.
    if (not utils.raises(ValueError, ipaddress.ip_address, host) and
            host in urlstr):
        return True

    tld = r'\.([^.0-9_-]+|xn--[a-z0-9-]+)$'
    forbidden = r'[\u0000-\u002c\u002f\u003a-\u0060\u007b-\u00b6]'
    return bool(re.search(tld, host) and not re.search(forbidden, host))


def _is_url_dns(urlstr: str) -> bool:
    """Check if a URL is really a URL via DNS.

    Args:
        url: The URL to check for as a string.

    Return:
        True if the URL really is a URL, False otherwise.
    """
    url = QUrl.fromUserInput(urlstr)
    assert url.isValid()

    if (utils.raises(ValueError, ipaddress.ip_address, urlstr) and
            not QHostAddress(urlstr).isNull()):
        log.url.debug("Bogus IP URL -> False")
        # Qt treats things like "23.42" or "1337" or "0xDEAD" as valid URLs
        # which we don't want to.
        return False

    host = url.host()
    if not host:
        log.url.debug("URL has no host -> False")
        return False
    log.url.debug("Doing DNS request for {}".format(host))
    info = QHostInfo.fromName(host)
    return not info.error()


def fuzzy_url(urlstr: str,
              cwd: str = None,
              relative: bool = False,
              do_search: bool = True,
              force_search: bool = False) -> QUrl:
    """Get a QUrl based on a user input which is URL or search term.

    Args:
        urlstr: URL to load as a string.
        cwd: The current working directory, or None.
        relative: Whether to resolve relative files.
        do_search: Whether to perform a search on non-URLs.
        force_search: Whether to force a search even if the content can be
                      interpreted as a URL or a path.

    Return:
        A target QUrl to a search page or the original URL.
    """
    urlstr = urlstr.strip()
    path = get_path_if_valid(urlstr, cwd=cwd, relative=relative,
                             check_exists=True)

    if not force_search and path is not None:
        url = QUrl.fromLocalFile(path)
    elif force_search or (do_search and not is_url(urlstr)):
        # probably a search term
        log.url.debug("URL is a fuzzy search term")
        try:
            url = _get_search_url(urlstr)
        except ValueError:  # invalid search engine
            url = QUrl.fromUserInput(urlstr)
    else:  # probably an address
        log.url.debug("URL is a fuzzy address")
        url = QUrl.fromUserInput(urlstr)
    log.url.debug("Converting fuzzy term {!r} to URL -> {}".format(
        urlstr, url.toDisplayString()))
    ensure_valid(url)
    return url


def _has_explicit_scheme(url: QUrl) -> bool:
    """Check if a url has an explicit scheme given.

    Args:
        url: The URL as QUrl.
    """
    # Note that generic URI syntax actually would allow a second colon
    # after the scheme delimiter. Since we don't know of any URIs
    # using this and want to support e.g. searching for scoped C++
    # symbols, we treat this as not a URI anyways.
    return bool(url.isValid() and url.scheme() and
                (url.host() or url.path()) and
                not url.path().startswith(':'))


def is_special_url(url: QUrl) -> bool:
    """Return True if url is an about:... or other special URL.

    Args:
        url: The URL as QUrl.
    """
    if not url.isValid():
        return False
    special_schemes = ('about', 'qute', 'file')
    return url.scheme() in special_schemes


def is_url(urlstr: str) -> bool:
    """Check if url seems to be a valid URL.

    Args:
        urlstr: The URL as string.

    Return:
        True if it is a valid URL, False otherwise.
    """
    autosearch = config.val.url.auto_search

    log.url.debug("Checking if {!r} is a URL (autosearch={}).".format(
        urlstr, autosearch))

    urlstr = urlstr.strip()
    qurl = QUrl(urlstr)
    qurl_userinput = QUrl.fromUserInput(urlstr)

    if autosearch == 'never':
        # no autosearch, so everything is a URL unless it has an explicit
        # search engine.
        try:
            engine, _term = _parse_search_term(urlstr)
        except ValueError:
            return False
        else:
            return engine is None

    if not qurl_userinput.isValid():
        # This will also catch non-URLs containing spaces.
        return False

    if _has_explicit_scheme(qurl) and ' ' not in urlstr:
        # URLs with explicit schemes are always URLs
        log.url.debug("Contains explicit scheme")
        url = True
    elif (autosearch == 'schemeless' and
          (not _has_explicit_scheme(qurl) or ' ' in urlstr)):
        # When autosearch=schemeless, URLs must contain schemes to be valid
        log.url.debug("No explicit scheme in given URL, treating as non-URL")
        url = False
    elif qurl_userinput.host() in ['localhost', '127.0.0.1', '::1']:
        log.url.debug("Is localhost.")
        url = True
    elif is_special_url(qurl):
        # Special URLs are always URLs, even with autosearch=never
        log.url.debug("Is a special URL.")
        url = True
    elif autosearch == 'dns':
        log.url.debug("Checking via DNS check")
        # We want to use QUrl.fromUserInput here, as the user might enter
        # "foo.de" and that should be treated as URL here.
        url = ' ' not in qurl_userinput.userName() and _is_url_dns(urlstr)
    elif autosearch == 'naive':
        log.url.debug("Checking via naive check")
        url = ' ' not in qurl_userinput.userName() and _is_url_naive(urlstr)
    else:  # pragma: no cover
        raise ValueError("Invalid autosearch value")
    log.url.debug("url = {}".format(url))
    return url


def ensure_valid(url: QUrl) -> None:
    if not url.isValid():
        raise InvalidUrlError(url)


def invalid_url_error(url: QUrl, action: str) -> None:
    """Display an error message for a URL.

    Args:
        action: The action which was interrupted by the error.
    """
    if url.isValid():
        raise ValueError("Calling invalid_url_error with valid URL {}".format(
            url.toDisplayString()))
    errstring = get_errstring(
        url, "Trying to {} with invalid URL".format(action))
    message.error(errstring)


def raise_cmdexc_if_invalid(url: QUrl) -> None:
    """Check if the given QUrl is invalid, and if so, raise a CommandError."""
    try:
        ensure_valid(url)
    except InvalidUrlError as e:
        raise cmdutils.CommandError(str(e))


def get_path_if_valid(pathstr: str,
                      cwd: str = None,
                      relative: bool = False,
                      check_exists: bool = False) -> Optional[str]:
    """Check if path is a valid path.

    Args:
        pathstr: The path as string.
        cwd: The current working directory, or None.
        relative: Whether to resolve relative files.
        check_exists: Whether to check if the file
                      actually exists of filesystem.

    Return:
        The path if it is a valid path, None otherwise.
    """
    pathstr = pathstr.strip()
    log.url.debug("Checking if {!r} is a path".format(pathstr))
    expanded = os.path.expanduser(pathstr)

    if os.path.isabs(expanded):
        path: Optional[str] = expanded
    elif relative and cwd:
        path = os.path.join(cwd, expanded)
    elif relative:
        try:
            path = os.path.abspath(expanded)
        except OSError:
            path = None
    else:
        path = None

    if check_exists:
        if path is not None:
            try:
                if os.path.exists(path):
                    log.url.debug("URL is a local file")
                else:
                    path = None
            except UnicodeEncodeError:
                log.url.debug(
                    "URL contains characters which are not present in the "
                    "current locale")
                path = None

    return path


def filename_from_url(url: QUrl, fallback: str = None) -> Optional[str]:
    """Get a suitable filename from a URL.

    Args:
        url: The URL to parse, as a QUrl.
        fallback: Value to use if no name can be determined.

    Return:
        The suggested filename as a string, or None.
    """
    if not url.isValid():
        return fallback

    if url.scheme().lower() == 'data':
        mimetype, _encoding = mimetypes.guess_type(url.toString())
        if not mimetype:
            return fallback

        ext = utils.mimetype_extension(mimetype) or ''
        return 'download' + ext

    pathname = posixpath.basename(url.path())
    if pathname:
        return pathname
    elif url.host():
        return url.host() + '.html'
    else:
        return fallback


HostTupleType = Tuple[str, str, int]


def host_tuple(url: QUrl) -> HostTupleType:
    """Get a (scheme, host, port) tuple from a QUrl.

    This is suitable to identify a connection, e.g. for SSL errors.
    """
    ensure_valid(url)
    scheme, host, port = url.scheme(), url.host(), url.port()
    assert scheme
    if not host:
        raise ValueError("Got URL {} without host.".format(
            url.toDisplayString()))
    if port == -1:
        port_mapping = {
            'http': 80,
            'https': 443,
            'ftp': 21,
        }
        try:
            port = port_mapping[scheme]
        except KeyError:
            raise ValueError("Got URL {} with unknown port.".format(
                url.toDisplayString()))
    return scheme, host, port


def get_errstring(url: QUrl, base: str = "Invalid URL") -> str:
    """Get an error string for a URL.

    Args:
        url: The URL as a QUrl.
        base: The base error string.

    Return:
        A new string with url.errorString() is appended if available.
    """
    url_error = url.errorString()
    if url_error:
        return base + " - {}".format(url_error)
    else:
        return base


def same_domain(url1: QUrl, url2: QUrl) -> bool:
    """Check if url1 and url2 belong to the same website.

    This will use a "public suffix list" to determine what a "top level domain"
    is. All further domains are ignored.

    For example example.com and www.example.com are considered the same. but
    example.co.uk and test.co.uk are not.

    If the URL's schemes or ports are different, they are always treated as not equal.

    Return:
        True if the domains are the same, False otherwise.
    """
    ensure_valid(url1)
    ensure_valid(url2)

    if url1.scheme() != url2.scheme():
        return False
    if url1.port() != url2.port():
        return False

    suffix1 = url1.topLevelDomain()
    suffix2 = url2.topLevelDomain()
    if not suffix1:
        return url1.host() == url2.host()

    if suffix1 != suffix2:
        return False

    domain1 = url1.host()[:-len(suffix1)].split('.')[-1]
    domain2 = url2.host()[:-len(suffix2)].split('.')[-1]
    return domain1 == domain2


def encoded_url(url: QUrl) -> str:
    """Return the fully encoded url as string.

    Args:
        url: The url to encode as QUrl.
    """
    return url.toEncoded().data().decode('ascii')


def file_url(path: str) -> str:
    """Return a file:// url (as string) to the given local path.

    Arguments:
        path: The absolute path to the local file
    """
    url = QUrl.fromLocalFile(path)
    return url.toString(QUrl.FullyEncoded)  # type: ignore[arg-type]


def data_url(mimetype: str, data: bytes) -> QUrl:
    """Get a data: QUrl for the given data."""
    b64 = base64.b64encode(data).decode('ascii')
    url = QUrl('data:{};base64,{}'.format(mimetype, b64))
    qtutils.ensure_valid(url)
    return url


def safe_display_string(qurl: QUrl) -> str:
    """Get a IDN-homograph phishing safe form of the given QUrl.

    If we're dealing with a Punycode-encoded URL, this prepends the hostname in
    its encoded form, to make sure those URLs are distinguishable.

    See https://github.com/qutebrowser/qutebrowser/issues/2547
    and https://bugreports.qt.io/browse/QTBUG-60365
    """
    ensure_valid(qurl)

    host = qurl.host(QUrl.FullyEncoded)
    assert '..' not in host, qurl  # https://bugreports.qt.io/browse/QTBUG-60364

    for part in host.split('.'):
        url_host = qurl.host(QUrl.FullyDecoded)
        if part.startswith('xn--') and host != url_host:
            return '({}) {}'.format(host, qurl.toDisplayString())

    return qurl.toDisplayString()


class InvalidProxyTypeError(Exception):

    """Error raised when proxy_from_url gets an unknown proxy type."""

    def __init__(self, typ: str) -> None:
        super().__init__("Invalid proxy type {}!".format(typ))


def proxy_from_url(url: QUrl) -> Union[QNetworkProxy, pac.PACFetcher]:
    """Create a QNetworkProxy from QUrl and a proxy type.

    Args:
        url: URL of a proxy (possibly with credentials).

    Return:
        New QNetworkProxy.
    """
    ensure_valid(url)

    scheme = url.scheme()
    if scheme in ['pac+http', 'pac+https', 'pac+file']:
        fetcher = pac.PACFetcher(url)
        fetcher.fetch()
        return fetcher

    types = {
        'http': QNetworkProxy.HttpProxy,
        'socks': QNetworkProxy.Socks5Proxy,
        'socks5': QNetworkProxy.Socks5Proxy,
        'direct': QNetworkProxy.NoProxy,
    }
    if scheme not in types:
        raise InvalidProxyTypeError(scheme)

    proxy = QNetworkProxy(types[scheme], url.host())

    if url.port() != -1:
        proxy.setPort(url.port())
    if url.userName():
        proxy.setUser(url.userName())
    if url.password():
        proxy.setPassword(url.password())
    return proxy


def parse_javascript_url(url: QUrl) -> str:
    """Get JavaScript source from the given URL.

    See https://wiki.whatwg.org/wiki/URL_schemes#javascript:_URLs
    and https://github.com/whatwg/url/issues/385
    """
    ensure_valid(url)
    if url.scheme() != 'javascript':
        raise Error("Expected a javascript:... URL")
    if url.authority():
        raise Error("URL contains unexpected components: {}"
                    .format(url.authority()))

    urlstr = url.toString(QUrl.FullyEncoded)  # type: ignore[arg-type]
    urlstr = urllib.parse.unquote(urlstr)

    code = urlstr[len('javascript:'):]
    if not code:
        raise Error("Resulted in empty JavaScript code")

    return code
