# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os
import pytest
from qutebrowser.utils import javascript
from qutebrowser.browser import shared
from qutebrowser.config import config
from PyQt5.QtWebEngineWidgets import QWebEngineSettings

DEFAULT_BODY_BG = "rgba(0, 0, 0, 0)"

class StylesheetTester:

    """Helper class (for the caret_tester fixture) for asserts.

    Attributes:
        js: The js_tester fixture.
    """

    def __init__(self, js_tester):
        self.js = js_tester

    def init_stylesheet(self):
        """Initializes stylesheet.
        Run after document is loaded."""
        self.js.run('window._qutebrowser = window._qutebrowser || {};', {})
        self.js.run_file('stylesheet.js', {})

    def set_css(self, css):
        """Set css to CSS via stylesheet.js."""
        code = javascript.assemble('stylesheet', 'set_css', css)
        self.js.run(code, None)

    def check_set(self, element, value):
        """Check whether the css in ELEMENT is set to VALUE."""
        self.js.run("window.getComputedStyle(document.body, null)"
                    ".getPropertyValue('{}');".format(element), value)


@pytest.fixture
def stylesheet_tester(js_tester_webengine):
    """Helper fixture to test caret browsing positions."""
    ss_tester = StylesheetTester(js_tester_webengine)
    # Showing webview here is necessary for test_scrolled_down_img to
    # succeed in some cases, see #1988
    ss_tester.js.webview.show()
    return ss_tester

def test_no_set_stylesheet(stylesheet_tester):
    stylesheet_tester.js.load('stylesheet/simple.html')
    stylesheet_tester.init_stylesheet()
    stylesheet_tester.check_set("background-color", DEFAULT_BODY_BG)

def test_no_set_stylesheet_no_load(stylesheet_tester):
    stylesheet_tester.js.load('stylesheet/simple.html')
    stylesheet_tester.check_set("background-color", DEFAULT_BODY_BG)

def test_simple_set_bg(stylesheet_tester):
    stylesheet_tester.js.load('stylesheet/simple.html')
    stylesheet_tester.init_stylesheet()
    stylesheet_tester.set_css("body {background-color: rgb(10, 10, 10);}")
    stylesheet_tester.check_set("background-color", "rgb(10, 10, 10)")

def test_simple_set_clear_bg(stylesheet_tester):
    stylesheet_tester.js.load('stylesheet/simple.html')
    stylesheet_tester.init_stylesheet()
    stylesheet_tester.set_css("body {background-color: rgb(10, 10, 10);}")
    stylesheet_tester.check_set("background-color", "rgb(10, 10, 10)")
    stylesheet_tester.set_css("")
    stylesheet_tester.check_set("background-color", DEFAULT_BODY_BG)
