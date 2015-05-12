# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""pylint conftest file for javascript test."""

import os
import os.path

import pytest
import jinja2
from PyQt5.QtWebKit import QWebSettings
from PyQt5.QtWebKitWidgets import QWebView

import qutebrowser


class JSTester:

    """Object returned by js_tester which provides test data and a webview.

    Attributes:
        webview: The webview which is used.
        _qtbot: The QtBot fixture from pytest-qt.
        _jinja_env: The jinja2 environment used to get templates.
    """

    def __init__(self, webview, qtbot):
        self.webview = webview
        self._qtbot = qtbot
        loader = jinja2.FileSystemLoader(os.path.dirname(__file__))
        self._jinja_env = jinja2.Environment(loader=loader, autoescape=True)

    def scroll_anchor(self, name):
        """Scroll the main frame to the given anchor."""
        page = self.webview.page()
        with self._qtbot.waitSignal(page.scrollRequested):
            page.mainFrame().scrollToAnchor(name)

    def load(self, path):
        """Load and display the given test data.

        Args:
            path: The path to the test file, relative to the javascript/
                  folder.
        """
        template = self._jinja_env.get_template(path)
        with self._qtbot.waitSignal(self.webview.loadFinished):
            self.webview.setHtml(template.render())

    def run_file(self, filename):
        """Run a javascript file.

        Args:
            filename: The javascript filename, relative to
                      qutebrowser/javascript.

        Return:
            The javascript return value.
        """
        base_path = os.path.join(os.path.dirname(qutebrowser.__file__),
                                 'javascript')
        full_path = os.path.join(base_path, filename)
        with open(full_path, 'r', encoding='utf-8') as f:
            source = f.read()
        return self.run(source)

    def run(self, source):
        """Run the given javascript source.

        Args:
            source: The source to run as a string.

        Return:
            The javascript return value.
        """
        assert self.webview.settings().testAttribute(
            QWebSettings.JavascriptEnabled)
        return self.webview.page().mainFrame().evaluateJavaScript(source)


@pytest.fixture
def js_tester(qtbot):
    """Fixture to test javascript snippets.

    Provides a QWebView with a 640x480px size and a JSTester instance.

    Args:
        qtbot: pytestqt.plugin.QtBot fixture.
    """
    webview = QWebView()
    qtbot.add_widget(webview)
    webview.resize(640, 480)
    return JSTester(webview, qtbot)
