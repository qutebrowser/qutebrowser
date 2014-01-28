from PyQt5.QtCore import QUrl


def qurl(url):
    if isinstance(url, QUrl):
        return url
    if not url.startswith('http://'):
        url = 'http://' + url
    return QUrl(url)
