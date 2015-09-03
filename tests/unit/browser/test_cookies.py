# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Alexander Cogneau (acogneau) <alexander.cogneau@gmail.com>:
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

"""Tests for qutebrowser.browser.cookies"""

from unittest import mock

from PyQt5.QtNetwork import QNetworkCookie
from PyQt5.QtTest import QSignalSpy
from PyQt5.QtCore import QUrl
import pytest

from qutebrowser.browser import cookies
from qutebrowser.utils import objreg
from qutebrowser.misc import lineparser

CONFIG_ALL_COOKIES = {'content': {'cookies-accept': 'all'}}
CONFIG_NEVER_COOKIES = {'content': {'cookies-accept': 'never'}}
CONFIG_COOKIES_ENABLED = {'content': {'cookies-store': True}}
CONFIG_COOKIES_DISABLED = {'content': {'cookies-store': False}}


cookie1 = b'foo1=bar; expires=Tue, 01-Jan-2036 08:00:01 GMT'
cookie2 = b'foo2=bar; expires=Tue, 01-Jan-2036 08:00:01 GMT'
session_cookie = b'foo3=bar'
expired_cookie = b'foo4=bar; expires=Sat, 01-Jan-2000 08:00:01 GMT'


class LineparserSaveStub(lineparser.LineParser):
    """A stub for LineParser's save()

    Attributes:
        saved: The .data before save()
    """

    def save(self):
        self.saved = self.data
        super().save()


@pytest.yield_fixture
def fake_save_manager():
    """Create a mock of save-manager and register it into objreg."""
    fake_save_manager = mock.Mock()
    objreg.register('save-manager', fake_save_manager)
    yield
    objreg.delete('save-manager')

"""Tests for RAMCookieJar."""


def test_set_cookies_accept(config_stub, qtbot, monkeypatch):
    """Test setCookiesFromUrl with cookies enabled."""
    config_stub.data = CONFIG_ALL_COOKIES
    ram_jar = cookies.RAMCookieJar()
    cookie = QNetworkCookie(b'foo', b'bar')
    url = QUrl('http://example.com/')
    with qtbot.waitSignal(ram_jar.changed, raising=True):
        assert ram_jar.setCookiesFromUrl([cookie], url)

    # assert the cookies are added correctly
    all_cookies = ram_jar.cookiesForUrl(url)
    assert len(all_cookies) == 1
    saved_cookie = all_cookies[0]
    assert (saved_cookie.name(),
            saved_cookie.value()) == (cookie.name(), cookie.value())


def test_set_cookies_never_accept(config_stub):
    """Test setCookiesFromUrl when cookies are not accepted."""
    config_stub.data = CONFIG_NEVER_COOKIES
    ram_jar = cookies.RAMCookieJar()
    error_signal_spy = QSignalSpy(ram_jar.changed)

    assert not ram_jar.setCookiesFromUrl('test', 'test')
    assert len(error_signal_spy) == 0


def test_cookie_jar_init(config_stub, fake_save_manager):
    """Test the CookieJar constructor."""
    line_parser_stub = [cookie1, cookie2]
    jar = cookies.CookieJar(line_parser=line_parser_stub)
    assert objreg.get('save-manager').add_saveable.called

    # Test that cookies are added to the jar
    assert len(jar.allCookies()) == 2
    assert jar.allCookies()[0].toRawForm().data() == cookie1
    assert jar.allCookies()[1].toRawForm().data() == cookie2


def test_purge_old_cookies(config_stub, fake_save_manager):
    """Test that expired cookies are deleted."""
    line_parser_stub = [cookie1, cookie2, session_cookie, expired_cookie]
    jar = cookies.CookieJar(line_parser=line_parser_stub)

    assert len(jar.allCookies()) == 4
    jar.purge_old_cookies()
    assert len(jar.allCookies()) == 3
    assert jar.allCookies()[0].toRawForm().data() == cookie1
    assert jar.allCookies()[1].toRawForm().data() == cookie2
    assert jar.allCookies()[2].toRawForm().data() == session_cookie


def test_save(config_stub, fake_save_manager, monkeypatch):
    """Test that expired and session cookies are not saved."""
    monkeypatch.setattr(lineparser,
                        'LineParser', LineparserSaveStub)

    jar = cookies.CookieJar()
    jar._lineparser.data = [cookie1, cookie2, session_cookie, expired_cookie]

    # update the cookies on the jar itself
    jar.parse_cookies()
    jar.save()
    assert len(jar._lineparser.saved) == 2
    assert jar._lineparser.saved[0].data() == cookie1
    assert jar._lineparser.saved[1].data() == cookie2


def test_cookies_changed(config_stub, fake_save_manager, monkeypatch, qtbot):
    """Test that self.changed is emitted and cookies are not saved."""
    config_stub.data = CONFIG_COOKIES_ENABLED
    monkeypatch.setattr(lineparser,
                        'LineParser', LineparserSaveStub)
    jar = cookies.CookieJar()

    # Test that signal is emitted
    with qtbot.waitSignal(jar.changed, raising=True):
        config_stub.data == CONFIG_COOKIES_DISABLED

    # test that cookies aren't saved
    assert len(jar._lineparser.saved) == 0
