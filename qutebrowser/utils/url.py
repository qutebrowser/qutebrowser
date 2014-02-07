"""Utils regarding URL handling."""

import re
import socket
import logging
import ipaddress
import urllib.parse

from PyQt5.QtCore import QUrl

import qutebrowser.utils.config as config


def qurl(url):
    """Get a QUrl from an url string."""
    if isinstance(url, QUrl):
        logging.debug("url is already a qurl")
        return url
    return QUrl.fromUserInput(url)


def fuzzy_url(url):
    """Returns a QUrl based on an user input which is URL or search term."""
    u = url.toString() if isinstance(url, QUrl) else url
    if is_url(u):
        # probably an address
        logging.debug("url is a fuzzy address")
        newurl = QUrl.fromUserInput(u)
    else:  # probably a search term
        logging.debug("url is a fuzzy search term")
        try:
            newurl = QUrl.fromUserInput(_get_search_url(u))
        except ValueError:
            newurl = QUrl.fromUserInput(u)
    logging.debug('Converting fuzzy term {} to url -> {}'.format(
        u, newurl.url()))
    return newurl


def _get_search_url(txt):
    """Get a search engine URL for a text."""
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
        template = config.config.get('searchengines', '__default__',
                                     fallback=None)
        term = txt
        logging.debug('engine: default, term "{}"'.format(txt))
    if template is None or not term:
        raise ValueError
    return template.format(urllib.parse.quote(term))


def is_about_url(url):
    """Return True if url is an about:... or other special URL."""
    u = url.toString() if isinstance(url, QUrl) else url
    return u.replace('http://', '').startswith('about:')


def is_url(url):
    """Return True if url seems to be a valid URL."""
    logging.debug('Checking if "{}" is an URL'.format(url))
    if ' ' in url:
        # An URL will never contain a space
        logging.debug('Contains space -> no url')
        return False
    elif config.config.getboolean('general', 'addressbar_dns_lookup'):
        logging.debug('Checking via DNS')
        return _is_url_dns(url)
    else:
        logging.debug('Checking via naive check')
        return _is_url_naive(url)


def _is_url_naive(url):
    """Naive check if given url string is really an url."""
    PROTOCOLS = ['http://', 'https://']
    ip = _get_netloc(url)
    if not ip:
        is_ip = False
    else:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            is_ip = False
        else:
            is_ip = True
    return (any([url.startswith(proto) for proto in PROTOCOLS]) or
            '.' in url or is_about_url(url) or url == 'localhost'
            or is_ip)


def _is_url_dns(url):
    """Check if an url string is really an url via DNS."""
    # FIXME we could probably solve this in a nicer way by attempting to open
    # the page in the webview, and then open the search if that fails.
    netloc = _get_netloc(url)
    if not netloc:
        return False
    try:
        socket.gethostbyname(netloc)
    except socket.gaierror:
        return False
    else:
        return True


def _get_netloc(url):
    """Gets the host part of an url."""
    # FIXME better way to do this?
    if '://' in url:
        return urllib.parse.urlsplit(url).netloc
    else:
        return urllib.parse.urlsplit('http://' + url).netloc
