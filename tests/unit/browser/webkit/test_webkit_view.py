# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
webview = pytest.importorskip('qutebrowser.browser.webkit.webview')


@pytest.fixture
def real_webview(webkit_tab, qtbot):
    wv = webview.WebView(win_id=0, tab_id=0, tab=webkit_tab, private=False)
    qtbot.add_widget(wv)
    return wv


def test_background_color_none(config_stub, real_webview):
    config_stub.val.colors.webpage.bg = None
