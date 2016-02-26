# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Alexander Cogneau (acogneau) <alexander.cogneau@gmail.com>:
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

"""Tests for qutebrowser.browser.cookies."""

from unittest import mock

from PyQt5.QtNetwork import QNetworkCookie
from PyQt5.QtCore import QUrl
import pytest

from qutebrowser.browser import cookies
from qutebrowser.utils import objreg
from qutebrowser.misc import lineparser, savemanager

CONFIG_ALL_COOKIES = {'content': {'cookies-accept': 'all'}}
CONFIG_NEVER_COOKIES = {'content': {'cookies-accept': 'never'}}
CONFIG_COOKIES_ENABLED = {'content': {'cookies-store': True}}


COOKIE1 = b'foo1=bar; expires=Tue, 01-Jan-2036 08:00:01 GMT'
COOKIE2 = b'foo2=bar; expires=Tue, 01-Jan-2036 08:00:01 GMT'
SESSION_COOKIE = b'foo3=bar'
EXPIRED_COOKIE = b'foo4=bar; expires=Sat, 01-Jan-2000 08:00:01 GMT'


class LineparserSaveStub(lineparser.BaseLineParser):

    """A stub for LineParser's save().

    Attributes:
        data: The data before the write
        saved: The .data before save()
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saved = []
        self.data = []

    def save(self):
        self.saved = self.data

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, key):
        return self.data[key]


@pytest.yield_fixture
def fake_save_manager():
    """Create a mock of save-manager and register it into objreg."""
    fake_save_manager = mock.Mock(spec=savemanager.SaveManager)
    objreg.register('save-manager', fake_save_manager)
    yield
    objreg.delete('save-manager')


def test_set_cookies_accept(config_stub, qtbot, monkeypatch):
    """Test setCookiesFromUrl with cookies enabled."""
    config_stub.data = CONFIG_ALL_COOKIES
    ram_jar = cookies.RAMCookieJar()
    cookie = QNetworkCookie(b'foo', b'bar')
    url = QUrl('http://example.com/')
    with qtbot.waitSignal(ram_jar.changed):
        assert ram_jar.setCookiesFromUrl([cookie], url)

    # assert the cookies are added correctly
    all_cookies = ram_jar.cookiesForUrl(url)
    assert len(all_cookies) == 1
    saved_cookie = all_cookies[0]
    expected = cookie.name(), cookie.value()
    assert saved_cookie.name(), saved_cookie.value() == expected


def test_set_cookies_never_accept(qtbot, config_stub):
    """Test setCookiesFromUrl when cookies are not accepted."""
    config_stub.data = CONFIG_NEVER_COOKIES
    ram_jar = cookies.RAMCookieJar()

    url = QUrl('http://example.com/')

    with qtbot.assertNotEmitted(ram_jar.changed):
        assert not ram_jar.setCookiesFromUrl(url, 'test')
    assert not ram_jar.cookiesForUrl(url)


def test_cookie_jar_init(config_stub, fake_save_manager):
    """Test the CookieJar constructor."""
    line_parser_stub = [COOKIE1, COOKIE2]
    jar = cookies.CookieJar(line_parser=line_parser_stub)
    assert objreg.get('save-manager').add_saveable.called

    # Test that cookies are added to the jar
    assert len(jar.allCookies()) == 2
    raw_cookies = [c.toRawForm().data() for c in jar.allCookies()]
    assert raw_cookies == [COOKIE1, COOKIE2]


def test_purge_old_cookies(config_stub, fake_save_manager):
    """Test that expired cookies are deleted."""
    line_parser_stub = [COOKIE1, COOKIE2, SESSION_COOKIE, EXPIRED_COOKIE]
    jar = cookies.CookieJar(line_parser=line_parser_stub)

    assert len(jar.allCookies()) == 4

    jar.purge_old_cookies()

    # Test that old cookies are gone
    raw_cookies = [cookie.toRawForm().data() for cookie in jar.allCookies()]
    assert raw_cookies == [COOKIE1, COOKIE2, SESSION_COOKIE]


def test_save(config_stub, fake_save_manager, monkeypatch, qapp):
    """Test that expired and session cookies are not saved."""
    monkeypatch.setattr(lineparser,
                        'LineParser', LineparserSaveStub)

    jar = cookies.CookieJar()
    jar._lineparser.data = [COOKIE1, COOKIE2, SESSION_COOKIE, EXPIRED_COOKIE]

    # Update the cookies on the jar itself
    jar.parse_cookies()
    jar.save()
    saved_cookies = [cookie.data() for cookie in jar._lineparser.saved]
    assert saved_cookies == [COOKIE1, COOKIE2]


def test_cookies_changed_emit(config_stub, fake_save_manager,
                              monkeypatch, qtbot):
    """Test that self.changed is emitted."""
    config_stub.data = CONFIG_COOKIES_ENABLED
    monkeypatch.setattr(lineparser,
                        'LineParser', LineparserSaveStub)
    jar = cookies.CookieJar()

    with qtbot.waitSignal(jar.changed):
        config_stub.set('content', 'cookies-store', False)


@pytest.mark.parametrize('store_cookies,empty', [
    (True, False),
    (False, True)
])
def test_cookies_changed(config_stub, fake_save_manager, monkeypatch,
                         qtbot, store_cookies, empty):
    """Test that cookies are saved correctly."""
    config_stub.data = CONFIG_COOKIES_ENABLED
    monkeypatch.setattr(lineparser,
                        'LineParser', LineparserSaveStub)
    jar = cookies.CookieJar()
    jar._lineparser.data = [COOKIE1, COOKIE2]
    jar.parse_cookies()
    config_stub.set('content', 'cookies-store', store_cookies)

    if empty:
        assert not jar._lineparser.data
        assert not jar._lineparser.saved
    else:
        assert jar._lineparser.data
