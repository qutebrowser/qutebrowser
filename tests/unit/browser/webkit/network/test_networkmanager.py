# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from qutebrowser.browser.webkit.network import networkmanager
from qutebrowser.browser.webkit import cookies


pytestmark = pytest.mark.usefixtures('cookiejar_and_cache')


def test_init_with_private_mode(fake_args):
    nam = networkmanager.NetworkManager(win_id=0, tab_id=0, private=True)
    assert isinstance(nam.cookieJar(), cookies.RAMCookieJar)
    assert nam.cache() is None
