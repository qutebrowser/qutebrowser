# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import logging

import pytest
QtWebEngineWidgets = pytest.importorskip("PyQt5.QtWebEngineWidgets")
QWebEnginePage = QtWebEngineWidgets.QWebEnginePage
QWebEngineScriptCollection = QtWebEngineWidgets.QWebEngineScriptCollection
QWebEngineScript = QtWebEngineWidgets.QWebEngineScript

from qutebrowser.browser import greasemonkey
from qutebrowser.utils import usertypes
webenginetab = pytest.importorskip(
    "qutebrowser.browser.webengine.webenginetab")

pytestmark = pytest.mark.usefixtures('greasemonkey_manager')


class TestWebengineScripts:

    """Test the _WebEngineScripts utility class."""

    @pytest.fixture
    def webengine_scripts(self, webengine_tab):
        return webengine_tab._scripts

    def test_greasemonkey_undefined_world(self, webengine_scripts, caplog):
        """Make sure scripts with non-existent worlds are rejected."""
        scripts = [
            greasemonkey.GreasemonkeyScript(
                [('qute-js-world', 'Mars'), ('name', 'test')], None)
        ]

        with caplog.at_level(logging.ERROR, 'greasemonkey'):
            webengine_scripts._inject_greasemonkey_scripts(scripts)

        assert len(caplog.records) == 1
        msg = caplog.messages[0]
        assert "has invalid value for '@qute-js-world': Mars" in msg
        collection = webengine_scripts._widget.page().scripts().toList()
        assert not any(script.name().startswith('GM-')
                       for script in collection)

    @pytest.mark.parametrize("worldid", [-1, 257])
    def test_greasemonkey_out_of_range_world(self, worldid, webengine_scripts,
                                             caplog):
        """Make sure scripts with out-of-range worlds are rejected."""
        scripts = [
            greasemonkey.GreasemonkeyScript(
                [('qute-js-world', worldid), ('name', 'test')], None)
        ]

        with caplog.at_level(logging.ERROR, 'greasemonkey'):
            webengine_scripts._inject_greasemonkey_scripts(scripts)

        assert len(caplog.records) == 1
        msg = caplog.messages[0]
        assert "has invalid value for '@qute-js-world': " in msg
        assert "should be between 0 and" in msg
        collection = webengine_scripts._widget.page().scripts().toList()
        assert not any(script.name().startswith('GM-')
                       for script in collection)

    @pytest.mark.parametrize("worldid", [0, 10])
    def test_greasemonkey_good_worlds_are_passed(self, worldid,
                                                 webengine_scripts, caplog):
        """Make sure scripts with valid worlds have it set."""
        scripts = [
            greasemonkey.GreasemonkeyScript(
                [('name', 'foo'), ('qute-js-world', worldid)], None
            )
        ]

        with caplog.at_level(logging.ERROR, 'greasemonkey'):
            webengine_scripts._inject_greasemonkey_scripts(scripts)

        collection = webengine_scripts._widget.page().scripts()
        assert collection.toList()[-1].worldId() == worldid

    def test_greasemonkey_document_end_workaround(self, monkeypatch,
                                                  webengine_scripts):
        """Make sure document-end is forced when needed."""
        monkeypatch.setattr(greasemonkey.objects, 'backend',
                            usertypes.Backend.QtWebEngine)
        monkeypatch.setattr(greasemonkey.qtutils, 'version_check',
                            lambda version, exact=False, compiled=True:
                            True)

        scripts = [
            greasemonkey.GreasemonkeyScript([
                ('name', 'Iridium'),
                ('namespace', 'https://github.com/ParticleCore'),
                ('run-at', 'document-start'),
            ], None)
        ]

        webengine_scripts._inject_greasemonkey_scripts(scripts)

        collection = webengine_scripts._widget.page().scripts()
        script = collection.toList()[-1]
        assert script.injectionPoint() == QWebEngineScript.DocumentReady


def test_notification_permission_workaround():
    """Make sure the value for QWebEnginePage::Notifications is correct."""
    try:
        notifications = QWebEnginePage.Notifications
    except AttributeError:
        pytest.skip("No Notifications member")

    permissions = webenginetab._WebEnginePermissions
    assert permissions._options[notifications] == 'content.notifications'
    assert permissions._messages[notifications] == 'show notifications'
