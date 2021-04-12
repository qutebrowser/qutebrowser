# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Test webenginetab."""

import logging
import textwrap

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


class ScriptsHelper:

    """Helper to get the processed (usually Greasemonkey) scripts."""

    def __init__(self, tab):
        self._tab = tab

    def get_scripts(self, prefix='GM-'):
        return [
            s for s in self._tab._widget.page().scripts().toList()
            if s.name().startswith(prefix)
        ]

    def get_script(self):
        scripts = self.get_scripts()
        assert len(scripts) == 1
        return scripts[0]

    def inject(self, scripts):
        self._tab._scripts._inject_greasemonkey_scripts(scripts)
        return self.get_scripts()


class TestWebengineScripts:

    """Test the _WebEngineScripts utility class."""

    @pytest.fixture
    def scripts_helper(self, webengine_tab):
        return ScriptsHelper(webengine_tab)

    def test_greasemonkey_undefined_world(self, scripts_helper, caplog):
        """Make sure scripts with non-existent worlds are rejected."""
        scripts = [
            greasemonkey.GreasemonkeyScript(
                [('qute-js-world', 'Mars'), ('name', 'test')], None)
        ]

        with caplog.at_level(logging.ERROR, 'greasemonkey'):
            injected = scripts_helper.inject(scripts)

        assert len(caplog.records) == 1
        msg = caplog.messages[0]
        assert "has invalid value for '@qute-js-world': Mars" in msg

        assert not injected

    @pytest.mark.parametrize("worldid", [-1, 257])
    def test_greasemonkey_out_of_range_world(self, worldid, scripts_helper, caplog):
        """Make sure scripts with out-of-range worlds are rejected."""
        scripts = [
            greasemonkey.GreasemonkeyScript(
                [('qute-js-world', worldid), ('name', 'test')], None)
        ]

        with caplog.at_level(logging.ERROR, 'greasemonkey'):
            injected = scripts_helper.inject(scripts)

        assert len(caplog.records) == 1
        msg = caplog.messages[0]
        assert "has invalid value for '@qute-js-world': " in msg
        assert "should be between 0 and" in msg

        assert not injected

    @pytest.mark.parametrize("worldid", [0, 10])
    def test_greasemonkey_good_worlds_are_passed(self, worldid,
                                                 scripts_helper, caplog):
        """Make sure scripts with valid worlds have it set."""
        scripts = [
            greasemonkey.GreasemonkeyScript(
                [('name', 'foo'), ('qute-js-world', worldid)], None
            )
        ]

        with caplog.at_level(logging.ERROR, 'greasemonkey'):
            scripts_helper.inject(scripts)

        assert scripts_helper.get_script().worldId() == worldid

    def test_greasemonkey_document_end_workaround(self, monkeypatch, scripts_helper):
        """Make sure document-end is forced when needed."""
        monkeypatch.setattr(greasemonkey.objects, 'backend',
                            usertypes.Backend.QtWebEngine)

        scripts = [
            greasemonkey.GreasemonkeyScript([
                ('name', 'Iridium'),
                ('namespace', 'https://github.com/ParticleCore'),
                ('run-at', 'document-start'),
            ], None)
        ]
        scripts_helper.inject(scripts)

        script = scripts_helper.get_script()
        assert script.injectionPoint() == QWebEngineScript.DocumentReady

    @pytest.mark.parametrize('run_at, expected', [
        # UserScript::DocumentElementCreation
        ('document-start', QWebEngineScript.DocumentCreation),
        # UserScript::DocumentLoadFinished
        ('document-end', QWebEngineScript.DocumentReady),
        # UserScript::AfterLoad
        ('document-idle', QWebEngineScript.Deferred),
        # default according to https://wiki.greasespot.net/Metadata_Block#.40run-at
        (None, QWebEngineScript.DocumentReady),
    ])
    def test_greasemonkey_run_at_values(self, scripts_helper, run_at, expected):
        if run_at is None:
            script = """
                // ==UserScript==
                // @name qutebrowser test userscript
                // ==/UserScript==
            """
        else:
            script = f"""
                // ==UserScript==
                // @name qutebrowser test userscript
                // @run-at {run_at}
                // ==/UserScript==
            """

        script = textwrap.dedent(script.lstrip('\n'))
        scripts = [greasemonkey.GreasemonkeyScript.parse(script)]
        scripts_helper.inject(scripts)

        assert scripts_helper.get_script().injectionPoint() == expected


def test_notification_permission_workaround():
    """Make sure the value for QWebEnginePage::Notifications is correct."""
    try:
        notifications = QWebEnginePage.Notifications
    except AttributeError:
        pytest.skip("No Notifications member")

    permissions = webenginetab._WebEnginePermissions
    assert permissions._options[notifications] == 'content.notifications.enabled'
    assert permissions._messages[notifications] == 'show notifications'
