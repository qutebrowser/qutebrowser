# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Test webenginetab."""

from unittest import mock
import logging

from PyQt5.QtCore import QObject
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineScriptCollection
import pytest

from qutebrowser.browser.webengine.webenginetab import _WebEngineScripts
from qutebrowser.browser.greasemonkey import GreasemonkeyScript

pytestmark = pytest.mark.usefixtures('greasemonkey_manager')


class TestWebengineScripts:
    """Test the _WebEngineScripts utility class."""

    class FakeWidget(QObject):
        """Fake widget for _WebengineScripts to use."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.scripts = []
            self.page = mock.create_autospec(QWebEnginePage)
            self.scripts_mock = mock.create_autospec(
                QWebEngineScriptCollection
            )
            self.scripts_mock.toList.return_value = self.scripts
            self.page.return_value.scripts.return_value = self.scripts_mock

    def test_greasemonkey_undefined_world(self, fake_web_tab, caplog):
        """Make sure scripts with non-existent worlds are rejected."""
        uut = _WebEngineScripts(fake_web_tab)
        uut._widget = self.FakeWidget()
        scripts = [
            GreasemonkeyScript([('qute-js-world', 'Mars')], None)
        ]

        with caplog.at_level(logging.ERROR, 'greasemonkey'):
            uut._inject_greasemonkey_scripts(scripts)

        assert len(caplog.records) == 1
        msg = caplog.records[0].message
        assert "has invalid value for '@qute-js-world': Mars" in msg
        uut._widget.scripts_mock.insert.assert_not_called()

    @pytest.mark.parametrize("worldid", [
        -1, 257
    ])
    def test_greasemonkey_out_of_range_world(self, worldid,
                                             fake_web_tab, caplog):
        """Make sure scripts with out-of-range worlds are rejected."""
        uut = _WebEngineScripts(fake_web_tab)
        uut._widget = self.FakeWidget()
        scripts = [
            GreasemonkeyScript([('qute-js-world', worldid)], None)
        ]

        with caplog.at_level(logging.ERROR, 'greasemonkey'):
            uut._inject_greasemonkey_scripts(scripts)

        assert len(caplog.records) == 1
        msg = caplog.records[0].message
        assert "has invalid value for '@qute-js-world': " in msg
        assert "should be between 0 and" in msg
        uut._widget.scripts_mock.insert.assert_not_called()

    @pytest.mark.parametrize("worldid", [
        0, 10
    ])
    def test_greasemonkey_good_worlds_are_passed(self, worldid,
                                                 fake_web_tab, caplog):
        """Make sure scripts with valid worlds have it set."""
        uut = _WebEngineScripts(fake_web_tab)
        uut._widget = self.FakeWidget()
        scripts = [
            GreasemonkeyScript(
                [('name', 'foo'), ('qute-js-world', worldid)], None
            )
        ]

        with caplog.at_level(logging.ERROR, 'greasemonkey'):
            uut._inject_greasemonkey_scripts(scripts)

        calls = uut._widget.scripts_mock.insert.call_args_list
        assert len(calls) == 1
        assert calls[0][0][0].worldId() == worldid
