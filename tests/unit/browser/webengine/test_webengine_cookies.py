# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest
from PyQt5.QtCore import QUrl
pytest.importorskip('PyQt5.QtWebEngineCore')
from PyQt5.QtWebEngineCore import QWebEngineCookieStore

from qutebrowser.browser.webengine import cookies
from qutebrowser.utils import urlmatch


@pytest.fixture
def filter_request():
    try:
        request = QWebEngineCookieStore.FilterRequest()
        request.firstPartyUrl = QUrl('https://domain1.com')
        return request
    except AttributeError:
        pytest.skip("FilterRequest not available")


@pytest.mark.parametrize('setting, third_party, accepted', [
    ('all', False, True),
    ('never', False, False),
    ('no-3rdparty', False, True),
    ('no-3rdparty', True, False),
])
def test_accept_cookie(config_stub, filter_request, setting, third_party,
                       accepted):
    """Test that _accept_cookie respects content.cookies.accept."""
    config_stub.val.content.cookies.accept = setting
    filter_request.thirdParty = third_party
    assert cookies._accept_cookie(filter_request) == accepted


@pytest.mark.parametrize('setting, pattern_setting, third_party, accepted', [
    ('never', 'all', False, True),
    ('all', 'never', False, False),
    ('no-3rdparty', 'all', True, True),
    ('all', 'no-3rdparty', True, False),
])
def test_accept_cookie_with_pattern(config_stub, filter_request, setting,
                                    pattern_setting, third_party, accepted):
    """Test that _accept_cookie matches firstPartyUrl with the UrlPattern."""
    filter_request.thirdParty = third_party
    config_stub.set_str('content.cookies.accept', setting)
    config_stub.set_str('content.cookies.accept', pattern_setting,
                        pattern=urlmatch.UrlPattern('https://*.domain1.com'))
    assert cookies._accept_cookie(filter_request) == accepted


@pytest.mark.parametrize('global_value', ['never', 'all'])
def test_invalid_url(config_stub, filter_request, global_value):
    """Make sure we fall back to the global value with invalid URLs.

    This can happen when there's a cookie request from an iframe, e.g. here:
    https://developers.google.com/youtube/youtube_player_demo
    """
    config_stub.val.content.cookies.accept = global_value
    filter_request.firstPartyUrl = QUrl()
    accepted = global_value == 'all'
    assert cookies._accept_cookie(filter_request) == accepted
