# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
pytest.importorskip('qutebrowser.qt.webkitwidgets')

from qutebrowser.browser.webkit import webkitsettings


def test_parsed_user_agent(qapp):
    webkitsettings._init_user_agent()

    parsed = webkitsettings.parsed_user_agent
    assert parsed.upstream_browser_key == 'Version'
    assert parsed.qt_key == 'Qt'
