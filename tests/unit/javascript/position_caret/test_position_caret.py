# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for position_caret.js."""

import pytest

QWebSettings = pytest.importorskip("PyQt5.QtWebKit").QWebSettings
QWebPage = pytest.importorskip("PyQt5.QtWebKitWidgets").QWebPage


@pytest.fixture(autouse=True)
def enable_caret_browsing(qapp):
    """Fixture to enable caret browsing globally."""
    settings = QWebSettings.globalSettings()
    old_value = settings.testAttribute(QWebSettings.CaretBrowsingEnabled)
    settings.setAttribute(QWebSettings.CaretBrowsingEnabled, True)
    yield
    settings.setAttribute(QWebSettings.CaretBrowsingEnabled, old_value)


class CaretTester:

    """Helper class (for the caret_tester fixture) for asserts.

    Attributes:
        js: The js_tester fixture.
        _qtbot: The qtbot fixture.
    """

    def __init__(self, js_tester, qtbot):
        self.js = js_tester
        self._qtbot = qtbot

    def check(self):
        """Check whether the caret is before the MARKER text."""
        self.js.run_file('javascript/position_caret.js')
        self.js.tab.caret.toggle_selection()
        self.js.tab.caret.move_to_next_word()

        with self._qtbot.wait_callback() as callback:
            self.js.tab.caret.selection(lambda text: callback(text.rstrip()))
        callback.assert_called_with('MARKER')

    def check_scrolled(self):
        """Check if the page is scrolled down."""
        assert not self.js.tab.scroller.at_top()


@pytest.fixture
def caret_tester(js_tester_webkit, qtbot):
    """Helper fixture to test caret browsing positions."""
    caret_tester = CaretTester(js_tester_webkit, qtbot)
    # Showing webview here is necessary for test_scrolled_down_img to
    # succeed in some cases, see #1988
    caret_tester.js.tab.show()
    return caret_tester


@pytest.mark.integration
def test_simple(caret_tester):
    """Test with a simple (one-line) HTML text."""
    caret_tester.js.load('position_caret/simple.html')
    caret_tester.check()


@pytest.mark.integration
@pytest.mark.no_xvfb
def test_scrolled_down(caret_tester):
    """Test with multiple text blocks with the viewport scrolled down."""
    caret_tester.js.load('position_caret/scrolled_down.html')
    caret_tester.js.tab.scroller.to_anchor('anchor')
    caret_tester.check_scrolled()
    caret_tester.check()


@pytest.mark.integration
@pytest.mark.parametrize('style', ['visibility: hidden', 'display: none'])
def test_invisible(caret_tester, style):
    """Test with hidden text elements."""
    caret_tester.js.load('position_caret/invisible.html', style=style)
    caret_tester.check()


@pytest.mark.integration
@pytest.mark.no_xvfb
def test_scrolled_down_img(caret_tester):
    """Test with an image at the top with the viewport scrolled down."""
    caret_tester.js.load('position_caret/scrolled_down_img.html')
    caret_tester.js.tab.scroller.to_anchor('anchor')
    caret_tester.check_scrolled()
    caret_tester.check()
