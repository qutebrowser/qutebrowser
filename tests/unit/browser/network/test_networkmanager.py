# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.browser.networkmanager."""

import pytest

from qutebrowser.browser.network import networkmanager
from qutebrowser.browser import cookies

pytestmark = pytest.mark.usefixtures('cookiejar_and_cache')


class TestPrivateMode:

    def test_init_with_private_mode(self, config_stub):
        config_stub.data = {'general': {'private-browsing': True}}
        nam = networkmanager.NetworkManager(0, 0)
        assert isinstance(nam.cookieJar(), cookies.RAMCookieJar)

    def test_setting_private_mode_later(self, config_stub):
        config_stub.data = {'general': {'private-browsing': False}}
        nam = networkmanager.NetworkManager(0, 0)
        assert not isinstance(nam.cookieJar(), cookies.RAMCookieJar)
        config_stub.data = {'general': {'private-browsing': True}}
        nam.on_config_changed()
        assert isinstance(nam.cookieJar(), cookies.RAMCookieJar)
