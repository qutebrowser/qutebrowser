# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
from PyQt5.QtCore import QUrl
from unittest.mock import MagicMock
from qutebrowser.browser.webengine.cookies import _accept_cookie
from qutebrowser.utils.urlmatch import UrlPattern


def test_accept_cookie_with_pattern(config_stub):
    """
    Test that the request's firstPartyUrl is used for comparing against the
    setting's UrlPattern in
    """
    request = MagicMock()
    request.firstPartyUrl = QUrl('https://domain1.com')
    request.thirdParty = False

    config_stub.set_str('content.cookies.accept', 'never')
    config_stub.set_str('content.cookies.accept', 'all',
                        pattern=UrlPattern('https://*.domain1.com'))
    assert _accept_cookie(request)

    config_stub.set_str('content.cookies.accept', 'all')
    config_stub.set_str('content.cookies.accept', 'never',
                        pattern=UrlPattern('https://*.domain1.com'))
    assert not _accept_cookie(request)

    request.thirdParty = True

    config_stub.set_str('content.cookies.accept', 'no-3rdparty')
    config_stub.set_str('content.cookies.accept', 'all',
                        pattern=UrlPattern('https://*.domain1.com'))
    assert _accept_cookie(request)

    config_stub.set_str('content.cookies.accept', 'all')
    config_stub.set_str('content.cookies.accept', 'no-3rdparty',
                        pattern=UrlPattern('https://*.domain1.com'))
    assert not _accept_cookie(request)
