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

"""Utils regarding URL handling."""

import re
import os.path
import ipaddress
import posixpath
import urllib.parse

from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QHostInfo, QHostAddress

from qutebrowser.config import config, configexc
from qutebrowser.utils import log, qtutils, message, utils
from qutebrowser.commands import cmdexc


# FIXME: we probably could raise some exceptions on invalid URLs
# https://github.com/The-Compiler/qutebrowser/issues/108


class InvalidUrlError(ValueError):

    """Error raised if a function got an invalid URL.

    Inherits ValueError because that was the exception originally used for
    that, so there still might be some code around which checks for that.
    """

    def __init__(self, url):
        if url.isValid():
            raise ValueError("Got valid URL {}!".format(url.toDisplayString()))
        self.url = url
        self.msg = get_errstring(url)
        super().__init__(self.msg)


def _parse_search_term(s):
    """Get a search engine name and search term from a string.

    Args:
        s: The string to get a search engine for.

    Return:
        A (engine, term) tuple, where engine is None for the default engine.
    """
    m = re.search(r'(^\w+)\s+(.+)($|\s+)', s)
    if m:
        engine = m.group(1)
        try:
            config.get('searchengines', engine)
        except configexc.NoOptionError:
            engine = None
            term = s
        else:
            term = m.group(2).rstrip()
    else:
        engine = None
        term = s
    log.url.debug("engine {}, term '{}'".format(engine, term))
    return (engine, term)


def _get_search_url(txt):
    """Get a search engine URL for a text.

    Args:
        txt: Text to search for.

    Return:
        The search URL as a QUrl.
    """
    log.url.debug("Finding search engine for '{}'".format(txt))
    engine, term = _parse_search_term(txt)
    assert term
    if engine is None:
        template = config.get('searchengines', 'DEFAULT')
    else:
        template = config.get('searchengines', engine)
    url = qurl_from_user_input(template.format(urllib.parse.quote(term)))
    qtutils.ensure_valid(url)
    return url


def _is_url_naive(urlstr):
    """Naive check if given URL is really a URL.

    Args:
        urlstr: The URL to check for, as string.

    Return:
        True if the URL really is a URL, False otherwise.
    """
    url = qurl_from_user_input(urlstr)
    assert url.isValid()

    if not utils.raises(ValueError, ipaddress.ip_address, urlstr):
        # Valid IPv4/IPv6 address
        return True

    # Qt treats things like "23.42" or "1337" or "0xDEAD" as valid URLs
    # which we don't want to. Note we already filtered *real* valid IPs
    # above.
    if not QHostAddress(urlstr).isNull():
        return False

    if '.' in url.host():
        return True
    else:
        return False


def _is_url_dns(urlstr):
    """Check if a URL is really a URL via DNS.

    Args:
        url: The URL to check for as a string.

    Return:
        True if the URL really is a URL, False otherwise.
    """
    url = qurl_from_user_input(urlstr)
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


def fuzzy_url(urlstr, cwd=None, relative=False, do_search=True):
    """Get a QUrl based on a user input which is URL or search term.

    Args:
        urlstr: URL to load as a string.
        cwd: The current working directory, or None.
        relative: Whether to resolve relative files.
        do_search: Whether to perform a search on non-URLs.

    Return:
        A target QUrl to a search page or the original URL.
    """
    expanded = os.path.expanduser(urlstr)
    if os.path.isabs(expanded):
        path = expanded
    elif relative and cwd:
        path = os.path.join(cwd, expanded)
    elif relative:
        try:
            path = os.path.abspath(expanded)
        except OSError:
            path = None
    else:
        path = None

    stripped = urlstr.strip()
    if path is not None and os.path.exists(path):
        log.url.debug("URL is a local file")
        url = QUrl.fromLocalFile(path)
    elif (not do_search) or is_url(stripped):
        # probably an address
        log.url.debug("URL is a fuzzy address")
        url = qurl_from_user_input(urlstr)
    else:  # probably a search term
        log.url.debug("URL is a fuzzy search term")
        try:
            url = _get_search_url(urlstr)
        except ValueError:  # invalid search engine
            url = qurl_from_user_input(stripped)
    log.url.debug("Converting fuzzy term {} to URL -> {}".format(
                  urlstr, url.toDisplayString()))
    if do_search and config.get('general', 'auto-search'):
        qtutils.ensure_valid(url)
    else:
        if not url.isValid():
            raise InvalidUrlError(url)
    return url


def _has_explicit_scheme(url):
    """Check if an url has an explicit scheme given.

    Args:
        url: The URL as QUrl.
    """
    # Note that generic URI syntax actually would allow a second colon
    # after the scheme delimiter. Since we don't know of any URIs
    # using this and want to support e.g. searching for scoped C++
    # symbols, we treat this as not an URI anyways.
    return (url.isValid() and url.scheme()
            and not url.path().startswith(' ')
            and not url.path().startswith(':'))


def is_special_url(url):
    """Return True if url is an about:... or other special URL.

    Args:
        url: The URL as QUrl.
    """
    if not url.isValid():
        return False
    special_schemes = ('about', 'qute', 'file')
    return url.scheme() in special_schemes


def is_url(urlstr):
    """Check if url seems to be a valid URL.

    Args:
        urlstr: The URL as string.

    Return:
        True if it is a valid URL, False otherwise.
    """
    autosearch = config.get('general', 'auto-search')

    log.url.debug("Checking if '{}' is a URL (autosearch={}).".format(
                  urlstr, autosearch))

    urlstr = urlstr.strip()
    qurl = QUrl(urlstr)
    qurl_userinput = qurl_from_user_input(urlstr)

    if not autosearch:
        # no autosearch, so everything is a URL unless it has an explicit
        # search engine.
        engine, _term = _parse_search_term(urlstr)
        if engine is None:
            return True
        else:
            return False

    if not qurl_userinput.isValid():
        # This will also catch URLs containing spaces.
        return False

    if _has_explicit_scheme(qurl):
        # URLs with explicit schemes are always URLs
        log.url.debug("Contains explicit scheme")
        url = True
    elif qurl_userinput.host() in ('localhost', '127.0.0.1', '::1'):
        log.url.debug("Is localhost.")
        url = True
    elif is_special_url(qurl):
        # Special URLs are always URLs, even with autosearch=False
        log.url.debug("Is an special URL.")
        url = True
    elif autosearch == 'dns':
        log.url.debug("Checking via DNS check")
        # We want to use qurl_from_user_input here, as the user might enter
        # "foo.de" and that should be treated as URL here.
        url = _is_url_dns(urlstr)
    elif autosearch == 'naive':
        log.url.debug("Checking via naive check")
        url = _is_url_naive(urlstr)
    else:  # pragma: no cover
        raise ValueError("Invalid autosearch value")
    log.url.debug("url = {}".format(url))
    return url


def qurl_from_user_input(urlstr):
    """Get a QUrl based on a user input. Additionally handles IPv6 addresses.

    QUrl.fromUserInput handles something like '::1' as a file URL instead of an
    IPv6, so we first try to handle it as a valid IPv6, and if that fails we
    use QUrl.fromUserInput.

    WORKAROUND - https://bugreports.qt.io/browse/QTBUG-41089
    FIXME - Maybe https://codereview.qt-project.org/#/c/93851/ has a better way
            to solve this?
    https://github.com/The-Compiler/qutebrowser/issues/109

    Args:
        urlstr: The URL as string.

    Return:
        The converted QUrl.
    """
    # First we try very liberally to separate something like an IPv6 from the
    # rest (e.g. path info or parameters)
    match = re.match(r'\[?([0-9a-fA-F:.]+)\]?(.*)', urlstr.strip())
    if match:
        ipstr, rest = match.groups()
    else:
        ipstr = urlstr.strip()
        rest = ''
    # Then we try to parse it as an IPv6, and if we fail use
    # QUrl.fromUserInput.
    try:
        ipaddress.IPv6Address(ipstr)
    except ipaddress.AddressValueError:
        return QUrl.fromUserInput(urlstr)
    else:
        return QUrl('http://[{}]{}'.format(ipstr, rest))


def invalid_url_error(win_id, url, action):
    """Display an error message for an URL.

    Args:
        win_id: The window ID to show the error message in.
        action: The action which was interrupted by the error.
    """
    if url.isValid():
        raise ValueError("Calling invalid_url_error with valid URL {}".format(
            url.toDisplayString()))
    errstring = get_errstring(
        url, "Trying to {} with invalid URL".format(action))
    message.error(win_id, errstring)


def raise_cmdexc_if_invalid(url):
    """Check if the given QUrl is invalid, and if so, raise a CommandError."""
    if not url.isValid():
        raise cmdexc.CommandError(get_errstring(url))


def filename_from_url(url):
    """Get a suitable filename from an URL.

    Args:
        url: The URL to parse, as a QUrl.

    Return:
        The suggested filename as a string, or None.
    """
    if not url.isValid():
        return None
    pathname = posixpath.basename(url.path())
    if pathname:
        return pathname
    elif url.host():
        return url.host() + '.html'
    else:
        return None


def host_tuple(url):
    """Get a (scheme, host, port) tuple from a QUrl.

    This is suitable to identify a connection, e.g. for SSL errors.
    """
    if not url.isValid():
        raise InvalidUrlError(url)
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


def get_errstring(url, base="Invalid URL"):
    """Get an error string for an URL.

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


def same_domain(url1, url2):
    """Check if url1 and url2 belong to the same website.

    This will use a "public suffix list" to determine what a "top level domain"
    is. All further domains are ignored.

    For example example.com and www.example.com are considered the same. but
    example.co.uk and test.co.uk are not.

    Return:
        True if the domains are the same, False otherwise.
    """
    if not url1.isValid():
        raise InvalidUrlError(url1)
    if not url2.isValid():
        raise InvalidUrlError(url2)

    suffix1 = url1.topLevelDomain()
    suffix2 = url2.topLevelDomain()
    if suffix1 == '':
        return url1.host() == url2.host()

    if not suffix1 == suffix2:
        return False

    domain1 = url1.host()[:-len(suffix1)].split('.')[-1]
    domain2 = url2.host()[:-len(suffix2)].split('.')[-1]
    return domain1 == domain2


class IncDecError(Exception):

    """Exception raised by incdec_number on problems.

    Attributes:
        msg: The error message.
        url: The QUrl which caused the error.
    """

    def __init__(self, msg, url):
        super().__init__(msg)
        self.url = url
        self.msg = msg

    def __str__(self):
        return '{}: {}'.format(self.msg, self.url.toString())


def incdec_number(url, incdec):
    """Find a number in the url and increment or decrement it.

    Args:
        url: The current url
        incdec: Either 'increment' or 'decrement'

    Return:
        The new url with the number incremented/decremented.

    Raises IncDecError if the url contains no number.
    """
    if not url.isValid():
        raise InvalidUrlError(url)

    path = url.path()
    # Get the last number in a string
    match = re.match(r'(.*\D|^)(\d+)(.*)', path)
    if not match:
        raise IncDecError("No number found in URL!", url)
    pre, number, post = match.groups()
    # This should always succeed because we match \d+
    val = int(number)
    if incdec == 'decrement':
        if val <= 0:
            raise IncDecError("Can't decrement {}!".format(val), url)
        val -= 1
    elif incdec == 'increment':
        val += 1
    else:
        raise ValueError("Invalid value {} for indec!".format(incdec))
    new_path = ''.join([pre, str(val), post])
    # Make a copy of the QUrl so we don't modify the original
    new_url = QUrl(url)
    new_url.setPath(new_path)
    return new_url
