# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Check how Qt behaves when trying to execute JS."""


import pytest


@pytest.mark.parametrize('js_enabled, expected', [(True, 2.0), (False, None)])
def test_simple_js_webkit(webview, js_enabled, expected):
    """With QtWebKit, evaluateJavaScript works when JS is on."""
    # If we get there (because of the webview fixture) we can be certain
    # QtWebKit is available
    from PyQt5.QtWebKit import QWebSettings
    webview.settings().setAttribute(QWebSettings.JavascriptEnabled, js_enabled)
    result = webview.page().mainFrame().evaluateJavaScript('1 + 1')
    assert result == expected


@pytest.mark.parametrize('js_enabled, expected', [(True, 2.0), (False, 2.0)])
def test_element_js_webkit(webview, js_enabled, expected):
    """With QtWebKit, evaluateJavaScript on an element works with JS off."""
    # If we get there (because of the webview fixture) we can be certain
    # QtWebKit is available
    from PyQt5.QtWebKit import QWebSettings
    webview.settings().setAttribute(QWebSettings.JavascriptEnabled, js_enabled)
    elem = webview.page().mainFrame().documentElement()
    result = elem.evaluateJavaScript('1 + 1')
    assert result == expected


@pytest.mark.usefixtures('redirect_webengine_data')
@pytest.mark.parametrize('js_enabled, world, expected', [
    # main world
    (True, 0, 2.0),
    (False, 0, None),
    # application world
    (True, 1, 2.0),
    (False, 1, 2.0),
    # user world
    (True, 2, 2.0),
    (False, 2, 2.0),
])
def test_simple_js_webengine(qtbot, webengineview, qapp,
                             js_enabled, world, expected):
    """With QtWebEngine, runJavaScript works even when JS is off."""
    # If we get there (because of the webengineview fixture) we can be certain
    # QtWebEngine is available
    from PyQt5.QtWebEngineWidgets import QWebEngineSettings, QWebEngineScript

    assert world in [QWebEngineScript.MainWorld,
                     QWebEngineScript.ApplicationWorld,
                     QWebEngineScript.UserWorld]

    settings = webengineview.settings()
    settings.setAttribute(QWebEngineSettings.JavascriptEnabled, js_enabled)
    qapp.processEvents()

    page = webengineview.page()

    with qtbot.wait_callback() as callback:
        page.runJavaScript('1 + 1', world, callback)

    callback.assert_called_with(expected)
