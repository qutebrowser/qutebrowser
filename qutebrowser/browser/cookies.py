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

"""Handling of HTTP cookies."""

from PyQt5.QtNetwork import QNetworkCookie, QNetworkCookieJar
from PyQt5.QtCore import QStandardPaths, QDateTime

from qutebrowser.config import config
from qutebrowser.config.parsers import line as lineparser
from qutebrowser.utils import utils, standarddir, objreg


class RAMCookieJar(QNetworkCookieJar):

    """An in-RAM cookie jar."""

    def __repr__(self):
        return utils.get_repr(self, count=len(self.allCookies()))

    def setCookiesFromUrl(self, cookies, url):
        """Add the cookies in the cookies list to this cookie jar.

        Args:
            cookies: A list of QNetworkCookies.
            url: The URL to set the cookies for.

        Return:
            True if one or more cookies are set for 'url', otherwise False.
        """
        if config.get('content', 'cookies-accept') == 'never':
            return False
        else:
            return super().setCookiesFromUrl(cookies, url)


class CookieJar(RAMCookieJar):

    """A cookie jar saving cookies to disk.

    Attributes:
        _linecp: The LineConfigParser managing the cookies file.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        datadir = standarddir.get(QStandardPaths.DataLocation)
        self._linecp = lineparser.LineConfigParser(datadir, 'cookies',
                                                   binary=True)
        cookies = []
        for line in self._linecp:
            cookies += QNetworkCookie.parseCookies(line)
        self.setAllCookies(cookies)
        objreg.get('config').changed.connect(self.cookies_store_changed)

    def purge_old_cookies(self):
        """Purge expired cookies from the cookie jar."""
        # Based on:
        # http://qt-project.org/doc/qt-5/qtwebkitexamples-webkitwidgets-browser-cookiejar-cpp.html
        now = QDateTime.currentDateTime()
        cookies = [c for c in self.allCookies()
                   if c.isSessionCookie() or c.expirationDate() >= now]
        self.setAllCookies(cookies)

    def save(self):
        """Save cookies to disk."""
        if not config.get('content', 'cookies-store'):
            return
        self.purge_old_cookies()
        lines = []
        for cookie in self.allCookies():
            if not cookie.isSessionCookie():
                lines.append(cookie.toRawForm())
        self._linecp.data = lines
        self._linecp.save()

    @config.change_filter('content', 'cookies-store')
    def cookies_store_changed(self):
        """Delete stored cookies if cookies-store changed."""
        if not config.get('content', 'cookies-store'):
            self._linecp.data = []
            self._linecp.save()
