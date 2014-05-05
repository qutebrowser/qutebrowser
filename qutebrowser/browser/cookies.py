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

"""Handling of HTTP cookies."""

import qutebrowser.config.config as config
from qutebrowser.config.lineparser import LineConfigParser

from PyQt5.QtNetwork import QNetworkCookie, QNetworkCookieJar


cookiejar = None


def init(datadir):
    """Initialize the global cookie jar.

    Args:
        datadir: The directory to store the cookie file in.
    """
    global cookiejar
    cookiejar = CookieJar(datadir)


class CookieJar(QNetworkCookieJar):

    """Our own cookie jar to save cookies to disk if desired."""

    def __init__(self, datadir):
        super().__init__()
        self._linecp = LineConfigParser(datadir, 'cookies')
        cookies = []
        for line in self._linecp.data:
            cookies += QNetworkCookie.parseCookies(line.encode('utf-8'))
        self.setAllCookies(cookies)

    def setCookiesFromUrl(self, cookies, url):
        """Add the cookies in the cookies list to this cookie jar.

        Args:
            cookies: A list of QNetworkCookies.
            url: The URL to set the cookies for.

        Return:
            True if one or more cookies are set for url, otherwise False.
        """
        if config.get('network', 'accept-cookies') == 'never':
            return False
        else:
            return super().setCookiesFromUrl(cookies, url)

    def save(self):
        """Save cookies to disk."""
        lines = []
        for cookie in self.allCookies():
            if not cookie.isSessionCookie():
                lines.append(bytes(cookie.toRawForm()).decode('utf-8'))
        self._linecp.data = lines
        self._linecp.save()
