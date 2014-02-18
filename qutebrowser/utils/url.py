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
import socket
import logging
import urllib.parse

from PyQt5.QtCore import QUrl

import qutebrowser.utils.config as config


def qurl(url):
    """Get a QUrl from an url string."""
    return url if isinstance(url, QUrl) else QUrl(url)


def urlstring(url):
    """Return an QUrl as string.

    qurl -- URL as string or QUrl.

    """
    return url.toString() if isinstance(url, QUrl) else url


def fuzzy_url(url):
    """Return a QUrl based on an user input which is URL or search term.

    url -- URL to load as QUrl or string.

    """
    u = qurl(url)
    urlstr = urlstring(url)
    if is_url(u):
        # probably an address
        logging.debug("url is a fuzzy address")
        newurl = QUrl.fromUserInput(urlstr)
    else:  # probably a search term
        logging.debug("url is a fuzzy search term")
        try:
            newurl = _get_search_url(urlstr)
        except ValueError:  # invalid search engine
            newurl = QUrl.fromUserInput(urlstr)
    logging.debug('Converting fuzzy term {} to url -> {}'.format(
        urlstr, urlstring(newurl)))
    return newurl


def _get_search_url(txt):
    """Return a search engine URL (QUrl) for a text."""
    logging.debug('Finding search engine for "{}"'.format(txt))
    r = re.compile(r'(^|\s+)!(\w+)($|\s+)')
    m = r.search(txt)
    if m:
        engine = m.group(2)
        # FIXME why doesn't fallback work?!
        template = config.config.get('searchengines', engine, fallback=None)
        term = r.sub('', txt)
        logging.debug('engine {}, term "{}"'.format(engine, term))
    else:
        template = config.config.get('searchengines', 'DEFAULT',
                                     fallback=None)
        term = txt
        logging.debug('engine: default, term "{}"'.format(txt))
    if template is None or not term:
        raise ValueError
    return QUrl.fromUserInput(template.format(urllib.parse.quote(term)))


def is_about_url(url):
    """Return True if url (QUrl) is an about:... or other special URL."""
    return urlstring(url).replace('http://', '').startswith('about:')


def is_url(url):
    """Return True if url (QUrl) seems to be a valid URL."""
    urlstr = urlstring(url)
    logging.debug('Checking if "{}" is an URL'.format(urlstr))

    try:
        autosearch = config.config.getboolean('general', 'auto_search')
    except ValueError:
        autosearch = config.config.get('general', 'auto_search')
    else:
        if autosearch:
            autosearch = 'naive'
        else:
            autosearch = None

    if autosearch is None:
        # no autosearch, so everything is an URL.
        return True

    if ' ' in urlstr:
        # An URL will never contain a space
        logging.debug('Contains space -> no url')
        return False
    elif is_about_url(url):
        # About URLs are always URLs, even with autosearch=False
        logging.debug('Is an about URL.')
        return True
    elif autosearch == 'dns':
        logging.debug('Checking via DNS')
        return _is_url_dns(QUrl.fromUserInput(urlstr))
    elif autosearch == 'naive':
        logging.debug('Checking via naive check')
        return _is_url_naive(url)


def _is_url_naive(url):
    """Naive check if given url (QUrl) is really an url."""
    PROTOCOLS = ['http://', 'https://']
    u = urlstring(url)
    return (any(u.startswith(proto) for proto in PROTOCOLS) or '.' in u or
            u == 'localhost')


def _is_url_dns(url):
    """Check if an url (QUrl) is really an url via DNS."""
    # FIXME we could probably solve this in a nicer way by attempting to open
    # the page in the webview, and then open the search if that fails.
    host = url.host()
    logging.debug("DNS request for {}".format(host))
    if not host:
        return False
    try:
        socket.gethostbyname(host)
    except socket.gaierror:
        return False
    else:
        return True
