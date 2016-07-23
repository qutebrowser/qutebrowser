# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
from PyQt5.QtCore import pyqtSignal, QDateTime

from qutebrowser.config import config
from qutebrowser.utils import utils, standarddir, objreg
from qutebrowser.misc import lineparser


class RAMCookieJar(QNetworkCookieJar):

    """An in-RAM cookie jar.

    Signals:
        changed: Emitted when the cookie store was changed.
    """

    changed = pyqtSignal()

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
            self.changed.emit()
            return super().setCookiesFromUrl(cookies, url)


class CookieJar(RAMCookieJar):

    """A cookie jar saving cookies to disk.

    Attributes:
        _lineparser: The LineParser managing the cookies file.
    """

    def __init__(self, parent=None, *, line_parser=None):
        super().__init__(parent)

        if line_parser:
            self._lineparser = line_parser
        else:
            self._lineparser = lineparser.LineParser(
                standarddir.data(), 'cookies', binary=True, parent=self)
        self.parse_cookies()
        objreg.get('config').changed.connect(self.cookies_store_changed)
        objreg.get('save-manager').add_saveable(
            'cookies', self.save, self.changed,
            config_opt=('content', 'cookies-store'))

    def parse_cookies(self):
        """Parse cookies from lineparser and store them."""
        cookies = []
        for line in self._lineparser:
            cookies += QNetworkCookie.parseCookies(line)
        self.setAllCookies(cookies)

    def purge_old_cookies(self):
        """Purge expired cookies from the cookie jar."""
        # Based on:
        # http://doc.qt.io/qt-5/qtwebkitexamples-webkitwidgets-browser-cookiejar-cpp.html
        now = QDateTime.currentDateTime()
        cookies = [c for c in self.allCookies()
                   if c.isSessionCookie() or c.expirationDate() >= now]
        self.setAllCookies(cookies)

    def save(self):
        """Save cookies to disk."""
        self.purge_old_cookies()
        lines = []
        for cookie in self.allCookies():
            if not cookie.isSessionCookie():
                lines.append(cookie.toRawForm())
        self._lineparser.data = lines
        self._lineparser.save()

    @config.change_filter('content', 'cookies-store')
    def cookies_store_changed(self):
        """Delete stored cookies if cookies-store changed."""
        if not config.get('content', 'cookies-store'):
            self._lineparser.data = []
            self._lineparser.save()
            self.changed.emit()
