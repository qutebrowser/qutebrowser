# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Handling of HTTP cookies."""

from typing import Sequence

from PyQt5.QtNetwork import QNetworkCookie, QNetworkCookieJar
from PyQt5.QtCore import pyqtSignal, QDateTime

from qutebrowser.config import config
from qutebrowser.utils import utils, standarddir, objreg, log
from qutebrowser.misc import lineparser, objects


cookie_jar = None
ram_cookie_jar = None


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
        accept = config.instance.get('content.cookies.accept', url=url)

        if 'log-cookies' in objects.debug_flags:
            log.network.debug('Cookie on {} -> applying setting {}'
                              .format(url.toDisplayString(), accept))

        if accept == 'never':
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
        config.instance.changed.connect(self._on_cookies_store_changed)
        objreg.get('save-manager').add_saveable(
            'cookies', self.save, self.changed,
            config_opt='content.cookies.store')

    def parse_cookies(self):
        """Parse cookies from lineparser and store them."""
        cookies: Sequence[QNetworkCookie] = []
        for line in self._lineparser:
            line_cookies = QNetworkCookie.parseCookies(line)
            cookies += line_cookies  # type: ignore[operator]
        self.setAllCookies(cookies)

    def purge_old_cookies(self):
        """Purge expired cookies from the cookie jar."""
        # Based on:
        # https://doc.qt.io/archives/qt-5.5/qtwebkitexamples-webkitwidgets-browser-cookiejar-cpp.html
        now = QDateTime.currentDateTime()
        cookies = [c for c in self.allCookies()
                   if c.isSessionCookie() or
                   c.expirationDate() >= now]  # type: ignore[operator]
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

    @config.change_filter('content.cookies.store')
    def _on_cookies_store_changed(self):
        """Delete stored cookies if cookies.store changed."""
        if not config.val.content.cookies.store:
            self._lineparser.data = []
            self._lineparser.save()
            self.changed.emit()


def init(qapp):
    """Initialize the global cookie jars."""
    global cookie_jar, ram_cookie_jar
    cookie_jar = CookieJar(qapp)
    ram_cookie_jar = RAMCookieJar(qapp)
