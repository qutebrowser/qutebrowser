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
    return url.url() if isinstance(url, QUrl) else url


def fuzzy_url(url):
    """Return a QUrl based on an user input which is URL or search term.

    url -- URL to load as QUrl or string.

    """
    u = qurl(url)
    urlstr = urlstring(url)
    if (not config.config.getboolean('general', 'auto_search')) or is_url(u):
        # probably an address
        logging.debug("url is a fuzzy address")
        newurl = QUrl.fromUserInput(urlstr)
    else:  # probably a search term
        logging.debug("url is a fuzzy search term")
        try:
            newurl = _get_search_url(urlstr)
        except ValueError:  # invalid search engine
            newurl = QUrl.fromUserInput(urlstr)
    logging.debug('Converting fuzzy term {} to url -> {}'.format(urlstr,
                                                                 newurl.url()))
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
    logging.debug('Checking if "{}" is an URL'.format(url.url()))
    if ' ' in urlstring(url):
        # An URL will never contain a space
        logging.debug('Contains space -> no url')
        return False
    elif config.config.getboolean('general', 'addressbar_dns_lookup'):
        logging.debug('Checking via DNS')
        return _is_url_dns(QUrl.fromUserInput(urlstring(url)))
    else:
        logging.debug('Checking via naive check')
        return _is_url_naive(url)


def _is_url_naive(url):
    """Naive check if given url (QUrl) is really an url."""
    PROTOCOLS = ['http://', 'https://']
    u = urlstring(url)
    return (any(u.startswith(proto) for proto in PROTOCOLS) or '.' in u or
            is_about_url(url) or u == 'localhost')


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
