"""Utility functions"""

from PyQt5.QtCore import QUrl


def qurl(url):
    """Get a QUrl from an url string."""
    if isinstance(url, QUrl):
        return url
    if not url.startswith('http://'):
        url = 'http://' + url
    return QUrl(url)
