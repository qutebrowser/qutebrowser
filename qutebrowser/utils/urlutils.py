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

"""Utils regarding URL handling."""

import re
import os.path
import ipaddress
import posixpath
import urllib.parse

from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QHostInfo

from qutebrowser.config import config
from qutebrowser.utils import log, qtutils, message, utils
from qutebrowser.commands import cmdexc


# FIXME: we probably could raise some exceptions on invalid URLs
# https://github.com/The-Compiler/qutebrowser/issues/108


def _get_search_url(txt):
    """Get a search engine URL for a text.

    Args:
        txt: Text to search for.

    Return:
        The search URL as a QUrl.
    """
    log.url.debug("Finding search engine for '{}'".format(txt))
    r = re.compile(r'(^\w+)\s+(.+)($|\s+)')
    m = r.search(txt)
    if m:
        engine = m.group(1)
        try:
            template = config.get('searchengines', engine)
        except config.NoOptionError:
            template = config.get('searchengines', 'DEFAULT')
            term = txt
        else:
            term = m.group(2).rstrip()
            log.url.debug("engine {}, term '{}'".format(engine, term))
    else:
        template = config.get('searchengines', 'DEFAULT')
        term = txt
        log.url.debug("engine: default, term '{}'".format(txt))
    if not term:
        raise FuzzyUrlError("No search term given")
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
    try:
        ipaddress.ip_address(urlstr)
    except ValueError:
        pass
    else:
        # Valid IPv4/IPv6 address
        return True

    # Qt treats things like "23.42" or "1337" or "0xDEAD" as valid URLs
    # which we don't want to. Note we already filtered *real* valid IPs
    # above.
    if ((not utils.raises(ValueError, int, urlstr, 0)) or
            (not utils.raises(ValueError, float, urlstr))):
        return False

    if not url.isValid():
        return False
    elif '.' in url.host():
        return True
    elif url.host() == 'localhost':
        return True
    else:
        return False


def _is_url_dns(url):
    """Check if a URL is really a URL via DNS.

    Args:
        url: The URL to check for as QUrl, ideally via qurl_from_user_input.

    Return:
        True if the URL really is a URL, False otherwise.
    """
    if not url.isValid():
        return False
    host = url.host()
    log.url.debug("DNS request for {}".format(host))
    if not host:
        return False
    info = QHostInfo.fromName(host)
    return not info.error()


def fuzzy_url(urlstr, cwd=None):
    """Get a QUrl based on an user input which is URL or search term.

    Args:
        urlstr: URL to load as a string.
        cwd: The current working directory, or None.

    Return:
        A target QUrl to a searchpage or the original URL.
    """
    if cwd:
        path = os.path.join(cwd, os.path.expanduser(urlstr))
    else:
        path = os.path.abspath(os.path.expanduser(urlstr))
    stripped = urlstr.strip()
    if os.path.exists(path):
        log.url.debug("URL is a local file")
        url = QUrl.fromLocalFile(path)
    elif (not _has_explicit_scheme(QUrl(urlstr)) and
            os.path.exists(path)):
        # We do this here rather than in the first block because we first want
        # to make sure it's not an URL like http://, because os.path.abspath
        # would mangle that.
        log.url.debug("URL is a relative local file")
        url = QUrl.fromLocalFile(path)
    elif is_url(stripped):
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
    qtutils.ensure_valid(url)
    return url


def _has_explicit_scheme(url):
    """Check if an url has an explicit scheme given.

    Args:
        url: The URL as QUrl.
    """
    return url.isValid() and url.scheme() and not url.path().startswith(' ')


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

    if not autosearch:
        # no autosearch, so everything is a URL.
        return True

    if _has_explicit_scheme(qurl):
        # URLs with explicit schemes are always URLs
        log.url.debug("Contains explicit scheme")
        return True
    elif ' ' in urlstr:
        # A URL will never contain a space
        log.url.debug("Contains space -> no URL")
        return False
    elif is_special_url(qurl):
        # Special URLs are always URLs, even with autosearch=False
        log.url.debug("Is an special URL.")
        return True
    elif autosearch == 'dns':
        log.url.debug("Checking via DNS")
        # We want to use qurl_from_user_input here, as the user might enter
        # "foo.de" and that should be treated as URL here.
        return _is_url_dns(qurl_from_user_input(urlstr))
    elif autosearch == 'naive':
        log.url.debug("Checking via naive check")
        return _is_url_naive(urlstr)
    else:
        raise ValueError("Invalid autosearch value")


def qurl_from_user_input(urlstr):
    """Get a QUrl based on an user input. Additionally handles IPv6 addresses.

    QUrl.fromUserInput handles something like '::1' as a file URL instead of an
    IPv6, so we first try to handle it as a valid IPv6, and if that fails we
    use QUrl.fromUserInput.

    WORKAROUND - https://bugreports.qt-project.org/browse/QTBUG-41089
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
    errstring = "Trying to {} with invalid URL".format(action)
    if url.errorString():
        errstring += " - {}".format(url.errorString())
    message.error(win_id, errstring)


def raise_cmdexc_if_invalid(url):
    """Check if the given QUrl is invalid, and if so, raise a CommandError."""
    if not url.isValid():
        errstr = "Invalid URL {}".format(url.toDisplayString())
        url_error = url.errorString()
        if url_error:
            errstr += " - {}".format(url_error)
        raise cmdexc.CommandError(errstr)


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


class FuzzyUrlError(Exception):

    """Exception raised by fuzzy_url on problems."""

    pass
