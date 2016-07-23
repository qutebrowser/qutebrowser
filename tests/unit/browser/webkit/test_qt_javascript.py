# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWebKit import QWebSettings


class WebEngineJSChecker(QObject):

    """Check if a JS value provided by a callback is the expected one."""

    got_result = pyqtSignal(object)

    def __init__(self, qtbot, parent=None):
        super().__init__(parent)
        self._qtbot = qtbot

    def callback(self, result):
        """Callback which can be passed to runJavaScript."""
        self.got_result.emit(result)

    def check(self, expected):
        """Wait until the JS result arrived and compare it."""
        with self._qtbot.waitSignal(self.got_result) as blocker:
            pass
        assert blocker.args == [expected]


@pytest.mark.parametrize('js_enabled, expected', [(True, 2.0), (False, None)])
def test_simple_js_webkit(webview, js_enabled, expected):
    """With QtWebKit, evaluateJavaScript works when JS is on."""
    webview.settings().setAttribute(QWebSettings.JavascriptEnabled, js_enabled)
    result = webview.page().mainFrame().evaluateJavaScript('1 + 1')
    assert result == expected


@pytest.mark.parametrize('js_enabled, expected', [(True, 2.0), (False, 2.0)])
def test_element_js_webkit(webview, js_enabled, expected):
    """With QtWebKit, evaluateJavaScript on an element works with JS off."""
    webview.settings().setAttribute(QWebSettings.JavascriptEnabled, js_enabled)
    elem = webview.page().mainFrame().documentElement()
    result = elem.evaluateJavaScript('1 + 1')
    assert result == expected


@pytest.mark.usefixtures('redirect_xdg_data')
@pytest.mark.parametrize('js_enabled, expected', [(True, 2.0), (False, 2.0)])
def test_simple_js_webengine(qtbot, webengineview, js_enabled, expected):
    """With QtWebEngine, runJavaScript works even when JS is off."""
    # pylint: disable=no-name-in-module,useless-suppression
    # If we get there (because of the webengineview fixture) we can be certain
    # QtWebEngine is available
    from PyQt5.QtWebEngineWidgets import QWebEngineSettings
    webengineview.settings().setAttribute(QWebEngineSettings.JavascriptEnabled,
                                          js_enabled)

    checker = WebEngineJSChecker(qtbot)
    webengineview.page().runJavaScript('1 + 1', checker.callback)
    checker.check(expected)
