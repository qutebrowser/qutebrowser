# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Jay Kamat <jaygkamat@gmail.com>
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

QtWebEngineWidgets = pytest.importorskip("PyQt5.QtWebEngineWidgets")
QWebEngineProfile = QtWebEngineWidgets.QWebEngineProfile

from qutebrowser.utils import javascript


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
        """Initialize the stylesheet with a provided css file."""
        css_path = os.path.join(os.path.dirname(__file__), css_file)
        self.config_stub.val.content.user_stylesheets = css_path

    def set_css(self, css):
        """Set document style to `css` via stylesheet.js."""
        code = javascript.assemble('stylesheet', 'set_css', css)
        self.js.run(code, None)

    def check_set(self, value, css_style="background-color",
                  document_element="document.body"):
        """Check whether the css in ELEMENT is set to VALUE."""
        self.js.run("console.log({document});"
                    "window.getComputedStyle({document}, null)"
                    ".getPropertyValue({prop});".format(
                        document=document_element,
                        prop=javascript.to_js(css_style)),
                    value)

    def check_eq(self, one, two, true=True):
        """Check if one and two are equal."""
        self.js.run("{} === {};".format(one, two), true)


@pytest.fixture
def stylesheet_tester(js_tester_webengine, config_stub):
    """Helper fixture to test stylesheets."""
    ss_tester = StylesheetTester(js_tester_webengine, config_stub)
    ss_tester.js.tab.show()
    return ss_tester


@pytest.mark.parametrize('page', ['stylesheet/simple.html',
                                  'stylesheet/simple_bg_set_red.html'])
def test_set_delayed(stylesheet_tester, page):
    """Test a delayed invocation of set_css."""
    stylesheet_tester.js.load(page)
    stylesheet_tester.init_stylesheet("none.css")
    stylesheet_tester.set_css("body {background-color: rgb(0, 255, 0);}")
    stylesheet_tester.check_set("rgb(0, 255, 0)")


@pytest.mark.parametrize('page', ['stylesheet/simple.html',
                                  'stylesheet/simple_bg_set_red.html'])
def test_set_clear_bg(stylesheet_tester, page):
    """Test setting and clearing the stylesheet."""
    stylesheet_tester.js.load('stylesheet/simple.html')
    stylesheet_tester.init_stylesheet()
    stylesheet_tester.check_set(GREEN_BODY_BG)
    stylesheet_tester.set_css("")
    stylesheet_tester.check_set(DEFAULT_BODY_BG)


def test_set_xml(stylesheet_tester):
    """Test stylesheet is applied without altering xml files."""
    stylesheet_tester.js.load_file('stylesheet/simple.xml')
    stylesheet_tester.init_stylesheet()
    stylesheet_tester.check_set(GREEN_BODY_BG)
    stylesheet_tester.check_eq('"html"', "document.documentElement.nodeName")


def test_set_svg(stylesheet_tester):
    """Test stylesheet is applied for svg files."""
    stylesheet_tester.js.load_file('../../../misc/cheatsheet.svg')
    stylesheet_tester.init_stylesheet()
    stylesheet_tester.check_set(GREEN_BODY_BG,
                                document_element="document.documentElement")
    stylesheet_tester.check_eq('"svg"', "document.documentElement.nodeName")


@pytest.mark.skip(reason="Too flaky, see #3771")
def test_set_error(stylesheet_tester, config_stub):
    """Test stylesheet modifies file not found error pages."""
    config_stub.changed.disconnect()  # This test is flaky otherwise...
    stylesheet_tester.init_stylesheet()
    stylesheet_tester.js.tab._init_stylesheet()
    stylesheet_tester.js.load_file('non-existent.html', force=True)
    stylesheet_tester.check_set(GREEN_BODY_BG)


def test_appendchild(stylesheet_tester):
    stylesheet_tester.js.load('stylesheet/simple.html')
    stylesheet_tester.init_stylesheet()
    js_test_file_path = ('../tests/unit/javascript/stylesheet/'
                         'test_appendchild.js')
    stylesheet_tester.js.run_file(js_test_file_path, {})
