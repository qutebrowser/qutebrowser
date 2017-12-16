# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

pytest.importorskip('PyQt5.QtWebEngineWidgets')

from qutebrowser.browser.webengine import webenginesettings


@pytest.fixture(autouse=True)
def init_profiles(qapp, config_stub, cache_tmpdir, data_tmpdir):
    webenginesettings._init_profiles()


def test_big_cache_size(config_stub):
    """Make sure a too big cache size is handled correctly."""
    config_stub.val.content.cache.size = 2 ** 63 - 1
    webenginesettings._update_settings('content.cache.size')

    size = webenginesettings.default_profile.httpCacheMaximumSize()
    assert size == 2 ** 31 - 1
