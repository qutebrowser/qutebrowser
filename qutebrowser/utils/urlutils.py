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
import urllib.parse

from PyQt5.QtCore import QUrl
from PyQt5.QtNetwork import QHostInfo

from qutebrowser.config import config
from qutebrowser.utils import log, qtutils


# FIXME: we probably could raise some exceptions on invalid URLs


def _get_search_url(txt):
    """Get a search engine URL for a text.

    Args:
        txt: Text to search for.

    Return:
        The search URL as a QUrl.

    Raise:
        FuzzyUrlError if there is no template or no search term was found.
    """
    log.url.debug("Finding search engine for '{}'".format(txt))
    r = re.compile(r'(^|\s+)!(\w+)($|\s+)')
    m = r.search(txt)
    if m:
        engine = m.group(2)
        try:
            template = config.get('searchengines', engine)
        except config.NoOptionError:
            raise FuzzyUrlError("Search engine {} not found!".format(
                engine))
        term = r.sub('', txt)
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
    if re.search(r'^[0-9.]+$', urlstr):
        # Qt treats things like "23.42" or "1337" as valid URLs which we don't
        # want to. Note we already filtered *real* valid IPs above.
        return False
    elif not url.isValid():
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


def fuzzy_url(urlstr):
    """Get a QUrl based on an user input which is URL or search term.

    Args:
        urlstr: URL to load as a string.

    Return:
        A target QUrl to a searchpage or the original URL.
    """
    path = os.path.abspath(os.path.expanduser(urlstr))
    stripped = urlstr.strip()
    if os.path.exists(path):
        log.url.debug("URL is a local file")
        url = QUrl.fromLocalFile(path)
    elif (not _has_explicit_scheme(QUrl(urlstr)) and
            os.path.exists(os.path.abspath(path))):
        # We do this here rather than in the first block because we first want
        # to make sure it's not an URL like http://, because os.path.abspath
        # would mangle that.
        log.url.debug("URL is a relative local file")
        url = QUrl.fromLocalFile(os.path.abspath(path))
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
    return url.isValid() and url.scheme()


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

    Raise:
        ValueError if the autosearch config value is invalid.
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


class FuzzyUrlError(Exception):

    """Exception raised by fuzzy_url on problems."""

    pass
