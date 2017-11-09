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

"""Tests for stylesheet.js."""

import os
import pytest
from qutebrowser.utils import javascript, utils
from qutebrowser.browser import shared
from qutebrowser.config import config
from PyQt5.QtWebEngineWidgets import QWebEngineSettings, QWebEngineProfile, QWebEngineScript
import qutebrowser.browser.webengine.webenginesettings as webenginesettings

DEFAULT_BODY_BG = "rgba(0, 0, 0, 0)"
GREEN_BODY_BG = "rgb(0, 255, 0)"
CSS_BODY_GREEN = "body {background-color: rgb(0, 255, 0);}"
CSS_BODY_RED = "body {background-color: rgb(255, 0, 0);}"

class StylesheetTester:

    """Helper class (for the stylesheet_tester fixture) for asserts.

    Attributes:
        js: The js_tester fixture.
        config_stub: The config stub object.
    """

    def __init__(self, js_tester, config_stub):
        self.js = js_tester
        self.config_stub = config_stub

    def init_stylesheet(self, css_file="green.css"):

        self.config_stub.val.content.user_stylesheets = \
            os.path.join(os.path.dirname(__file__), css_file)
        p = QWebEngineProfile.defaultProfile()
        webenginesettings._init_stylesheet(p)

    def set_css(self, css):
        """Set css to CSS via stylesheet.js."""
        code = javascript.assemble('stylesheet', 'set_css', css)
        self.js.run(code, None)

    def check_set(self, value, element="background-color"):
        """Check whether the css in ELEMENT is set to VALUE."""
        self.js.run("window.getComputedStyle(document.body, null)"
                    ".getPropertyValue('{}');".format(element), value)


@pytest.fixture
def stylesheet_tester(js_tester_webengine, config_stub):
    """Helper fixture to test stylesheets"""
    ss_tester = StylesheetTester(js_tester_webengine, config_stub)
    ss_tester.js.webview.show()
    return ss_tester

@pytest.mark.parametrize('page', ['stylesheet/simple.html',
                                  'stylesheet/simple_bg_set_red.html'])
@pytest.mark.parametrize('set_js', [True, False])
def test_set_delayed(stylesheet_tester, page, set_js):
    """Test a delayed invocation of set_css."""
    stylesheet_tester.init_stylesheet("none.css")
    stylesheet_tester.js.load(page)
    if set_js:
        stylesheet_tester.js.run(
            'document.body.style.backgroundColor = "red";', 'red')
        pytest.xfail("overring values set with js does not work.")
    stylesheet_tester.set_css("body {background-color: rgb(0, 255, 0);}")
    stylesheet_tester.check_set("rgb(0, 255, 0)")

@pytest.mark.parametrize('page', ['stylesheet/simple.html',
                                  'stylesheet/simple_bg_set_red.html'])
def test_set_clear_bg(stylesheet_tester, page):
    """Test setting and clearing the stylesheet"""
    stylesheet_tester.init_stylesheet()
    stylesheet_tester.js.load('stylesheet/simple.html')
    stylesheet_tester.check_set(GREEN_BODY_BG)
    stylesheet_tester.set_css("")
    stylesheet_tester.check_set(DEFAULT_BODY_BG)

def test_no_set_xml(stylesheet_tester):
    """Test stylesheet never modifies xml files."""
    stylesheet_tester.init_stylesheet()
    pytest.xfail("loading xml/svg files throws exceptions")
    stylesheet_tester.js.load_file('stylesheet/simple.xml')
    stylesheet_tester.check_set(DEFAULT_BODY_BG)
    stylesheet_tester.set_css("body {background-color: rgb(0, 255, 0);}")
    stylesheet_tester.check_set(DEFAULT_BODY_BG)

def test_no_set_svg(stylesheet_tester):
    """Test stylesheet never modifies svg files."""
    stylesheet_tester.init_stylesheet()
    pytest.xfail("loading xml/svg files throws exceptions")
    stylesheet_tester.js.load_file('../../../misc/cheatsheet.svg')
    stylesheet_tester.check_set(None)
    stylesheet_tester.set_css("body {background-color: rgb(0, 255, 0);}")
    stylesheet_tester.check_set(None)
