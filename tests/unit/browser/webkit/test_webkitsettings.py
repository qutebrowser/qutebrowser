# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
pytest.importorskip('PyQt5.QtWebKitWidgets')

from qutebrowser.browser.webkit import webkitsettings


def test_parsed_user_agent(qapp):
    webkitsettings._init_user_agent()

    parsed = webkitsettings.parsed_user_agent
    assert parsed.upstream_browser_key == 'Version'
    assert parsed.qt_key == 'Qt'
