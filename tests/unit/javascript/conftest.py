# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""pytest conftest file for javascript tests."""

import pathlib
import pytest
import jinja2

from PyQt5.QtCore import QUrl

import qutebrowser
from qutebrowser.utils import usertypes

JS_DIR = pathlib.Path(__file__).parent


class JSTester:

    """Common subclass providing basic functionality for all JS testers.

    Attributes:
        tab: The tab object which is used.
        qtbot: The QtBot fixture from pytest-qt.
        _jinja_env: The jinja2 environment used to get templates.
    """

    def __init__(self, tab, qtbot, config_stub):
        self.tab = tab
        self.qtbot = qtbot
        loader = jinja2.FileSystemLoader(JS_DIR)
        self._jinja_env = jinja2.Environment(loader=loader, autoescape=True)
        # Make sure error logging via JS fails tests
        config_stub.val.content.javascript.log = {
            'info': 'info',
            'error': 'error',
            'unknown': 'error',
            'warning': 'error'
        }

    def load(self, path, base_url=QUrl(), **kwargs):
        """Load and display the given jinja test data.

        Args:
            path: The path to the test file, relative to the javascript/
                  folder.
            base_url: The url to pass to set_html.
            **kwargs: Passed to jinja's template.render().
        """
        template = self._jinja_env.get_template(path)

        try:
            with self.qtbot.wait_signal(self.tab.load_finished,
                                       timeout=2000) as blocker:
                self.tab.set_html(template.render(**kwargs), base_url=base_url)
        except self.qtbot.TimeoutError:
            # Sometimes this fails for some odd reason on macOS, let's just try
            # again.
            print("Trying to load page again...")
            with self.qtbot.wait_signal(self.tab.load_finished,
                                       timeout=2000) as blocker:
                self.tab.set_html(template.render(**kwargs), base_url=base_url)

        assert blocker.args == [True]

    def load_file(self, path: str, force: bool = False):
        """Load a file from disk.

        Args:
            path: The string path from disk to load (relative to this file)
            force: Whether to force loading even if the file is invalid.
        """
        self.load_url(QUrl.fromLocalFile(
            str(JS_DIR / path)), force)

    def load_url(self, url: QUrl, force: bool = False):
        """Load a given QUrl.

        Args:
            url: The QUrl to load.
            force: Whether to force loading even if the file is invalid.
        """
        with self.qtbot.wait_signal(self.tab.load_finished,
                                   timeout=2000) as blocker:
            self.tab.load_url(url)
        if not force:
            assert blocker.args == [True]

    def run_file(self, path: str, expected=None) -> None:
        """Run a javascript file.

        Args:
            path: The path to the JS file, relative to the qutebrowser package.
            expected: The value expected return from the javascript execution
        """
        base_path = pathlib.Path(qutebrowser.__file__).resolve().parent
        source = (base_path / path).read_text(encoding='utf-8')
        self.run(source, expected)

    def run(self, source: str, expected=usertypes.UNSET, world=None) -> None:
        """Run the given javascript source.

        Args:
            source: The source to run as a string.
            expected: The value expected return from the javascript execution
            world: The scope the javascript will run in
        """
        with self.qtbot.wait_callback() as callback:
            self.tab.run_js_async(source, callback, world=world)

        if expected is not usertypes.UNSET:
            callback.assert_called_with(expected)


@pytest.fixture
def js_tester_webkit(webkit_tab, qtbot, config_stub):
    """Fixture to test javascript snippets in webkit."""
    return JSTester(webkit_tab, qtbot, config_stub)


@pytest.fixture
def js_tester_webengine(webengine_tab, qtbot, config_stub):
    """Fixture to test javascript snippets in webengine."""
    return JSTester(webengine_tab, qtbot, config_stub)


@pytest.fixture
def js_tester(web_tab, qtbot, config_stub):
    """Fixture to test javascript snippets with both backends."""
    return JSTester(web_tab, qtbot, config_stub)
