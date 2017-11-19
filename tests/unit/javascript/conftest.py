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

"""pylint conftest file for javascript test."""

import os
import os.path
import logging

import pytest
import jinja2

from PyQt5.QtCore import QUrl

import helpers.utils
import qutebrowser.utils.debug
from qutebrowser.utils import utils

try:
    from PyQt5.QtWebKit import QWebSettings
    from PyQt5.QtWebKitWidgets import QWebPage
except ImportError:
    # FIXME:qtwebengine Make these tests use the tab API
    QWebSettings = None
    QWebPage = None

try:
    from PyQt5.QtWebEngineWidgets import (QWebEnginePage,
                                          QWebEngineSettings,
                                          QWebEngineScript)
except ImportError:
    QWebEnginePage = None
    QWebEngineSettings = None
    QWebEngineScript = None


if QWebPage is None:
    TestWebPage = None
else:
    class TestWebPage(QWebPage):

        """QWebPage subclass which overrides some test methods.

        Attributes:
            _logger: The logger used for alerts.
        """

        def __init__(self, parent=None):
            super().__init__(parent)
            self._logger = logging.getLogger('js-tests')

        def javaScriptAlert(self, _frame, msg):
            """Log javascript alerts."""
            self._logger.info("js alert: {}".format(msg))

        def javaScriptConfirm(self, _frame, msg):
            """Fail tests on js confirm() as that should never happen."""
            pytest.fail("js confirm: {}".format(msg))

        def javaScriptPrompt(self, _frame, msg, _default):
            """Fail tests on js prompt() as that should never happen."""
            pytest.fail("js prompt: {}".format(msg))

        def javaScriptConsoleMessage(self, msg, line, source):
            """Fail tests on js console messages as they're used for errors."""
            pytest.fail("js console ({}:{}): {}".format(source, line, msg))

if QWebEnginePage is None:
    TestWebEnginePage = None
else:
    class TestWebEnginePage(QWebEnginePage):

        """QWebEnginePage which overrides javascript logging methods.

        Attributes:
            _logger: The logger used for alerts.
        """

        def __init__(self, parent=None):
            super().__init__(parent)
            self._logger = logging.getLogger('js-tests')

        def javaScriptAlert(self, _frame, msg):
            """Log javascript alerts."""
            self._logger.info("js alert: {}".format(msg))

        def javaScriptConfirm(self, _frame, msg):
            """Fail tests on js confirm() as that should never happen."""
            pytest.fail("js confirm: {}".format(msg))

        def javaScriptPrompt(self, _frame, msg, _default):
            """Fail tests on js prompt() as that should never happen."""
            pytest.fail("js prompt: {}".format(msg))

        def javaScriptConsoleMessage(self, level, msg, line, source):
            """Fail tests on js console messages as they're used for errors."""
            pytest.fail("[{}] js console ({}:{}): {}".format(
                qutebrowser.utils.debug.qenum_key(
                    QWebEnginePage, level), source, line, msg))


class JSTester:

    """Common subclass providing basic functionality for all JS testers.

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

    def load(self, path, **kwargs):
        """Load and display the given jinja test data.

        Args:
            path: The path to the test file, relative to the javascript/
                  folder.
            **kwargs: Passed to jinja's template.render().
        """
        template = self._jinja_env.get_template(path)
        with self._qtbot.waitSignal(self.webview.loadFinished,
                                    timeout=2000) as blocker:
            self.webview.setHtml(template.render(**kwargs))
        assert blocker.args == [True]

    def load_file(self, path: str, force: bool = False):
        """Load a file from disk.

        Args:
            path: The string path from disk to load (relative to this file)
            force: Whether to force loading even if the file is invalid.
        """
        self.load_url(QUrl.fromLocalFile(
            os.path.join(os.path.dirname(__file__), path)), force)

    def load_url(self, url: QUrl, force: bool = False):
        """Load a given QUrl.

        Args:
            url: The QUrl to load.
            force: Whether to force loading even if the file is invalid.
        """
        with self._qtbot.waitSignal(self.webview.loadFinished,
                                    timeout=2000) as blocker:
            self.webview.load(url)
        if not force:
            assert blocker.args == [True]


class JSWebKitTester(JSTester):

    """Object returned by js_tester which provides test data and a webview.

    Attributes:
        webview: The webview which is used.
        _qtbot: The QtBot fixture from pytest-qt.
        _jinja_env: The jinja2 environment used to get templates.
    """

    def __init__(self, webview, qtbot):
        super().__init__(webview, qtbot)
        self.webview.setPage(TestWebPage(self.webview))

    def scroll_anchor(self, name):
        """Scroll the main frame to the given anchor."""
        page = self.webview.page()
        old_pos = page.mainFrame().scrollPosition()
        page.mainFrame().scrollToAnchor(name)
        new_pos = page.mainFrame().scrollPosition()
        assert old_pos != new_pos

    def run_file(self, filename):
        """Run a javascript file.

        Args:
            filename: The javascript filename, relative to
                      qutebrowser/javascript.

        Return:
            The javascript return value.
        """
        source = utils.read_file(os.path.join('javascript', filename))
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


class JSWebEngineTester(JSTester):

    """Object returned by js_tester_webengine which provides a webview.

    Attributes:
        webview: The webview which is used.
        _qtbot: The QtBot fixture from pytest-qt.
        _jinja_env: The jinja2 environment used to get templates.
    """

    def __init__(self, webview, qtbot):
        super().__init__(webview, qtbot)
        self.webview.setPage(TestWebEnginePage(self.webview))

    def run_file(self, filename: str, expected) -> None:
        """Run a javascript file.

        Args:
            filename: The javascript filename, relative to
                      qutebrowser/javascript.
            expected: The value expected return from the javascript execution
        """
        source = utils.read_file(os.path.join('javascript', filename))
        self.run(source, expected)

    def run(self, source: str, expected, world=None) -> None:
        """Run the given javascript source.

        Args:
            source: The source to run as a string.
            expected: The value expected return from the javascript execution
            world: The scope the javascript will run in
        """
        if world is None:
            world = QWebEngineScript.ApplicationWorld

        callback_checker = helpers.utils.CallbackChecker(self._qtbot)
        assert self.webview.settings().testAttribute(
            QWebEngineSettings.JavascriptEnabled)
        self.webview.page().runJavaScript(source, world,
                                          callback_checker.callback)
        callback_checker.check(expected)


@pytest.fixture
def js_tester_webkit(webview, qtbot):
    """Fixture to test javascript snippets in webkit."""
    return JSWebKitTester(webview, qtbot)


@pytest.fixture
def js_tester_webengine(callback_checker, webengineview, qtbot):
    """Fixture to test javascript snippets in webengine."""
    return JSWebEngineTester(webengineview, qtbot)
