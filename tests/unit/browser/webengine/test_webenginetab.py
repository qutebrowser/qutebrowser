# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test webenginetab."""

import logging
import textwrap

import pytest
QtWebEngineCore = pytest.importorskip("qutebrowser.qt.webenginecore")
QWebEnginePage = QtWebEngineCore.QWebEnginePage
QWebEngineScriptCollection = QtWebEngineCore.QWebEngineScriptCollection
QWebEngineScript = QtWebEngineCore.QWebEngineScript

from qutebrowser.browser import greasemonkey
from qutebrowser.utils import usertypes, utils, version
webenginetab = pytest.importorskip(
    "qutebrowser.browser.webengine.webenginetab")

pytestmark = pytest.mark.usefixtures('greasemonkey_manager')

versions = version.qtwebengine_versions(avoid_init=True)


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
        assert script.injectionPoint() == QWebEngineScript.InjectionPoint.DocumentReady

    @pytest.mark.parametrize('run_at, expected', [
        # UserScript::DocumentElementCreation
        ('document-start', QWebEngineScript.InjectionPoint.DocumentCreation),
        # UserScript::DocumentLoadFinished
        ('document-end', QWebEngineScript.InjectionPoint.DocumentReady),
        # UserScript::AfterLoad
        ('document-idle', QWebEngineScript.InjectionPoint.Deferred),
        # default according to https://wiki.greasespot.net/Metadata_Block#.40run-at
        (None, QWebEngineScript.InjectionPoint.DocumentReady),
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

    @pytest.mark.parametrize('header1, header2, expected_names', [
        (
            ["// @namespace ns1", "// @name same"],
            ["// @namespace ns2", "// @name same"],
            ['GM-ns1/same', 'GM-ns2/same'],
        ),
        (
            ["// @name same"],
            ["// @name same"],
            ['GM-same', 'GM-same-2'],
        ),
        (
            ["// @name same"],
            ["// @name sam"],
            ['GM-same', 'GM-sam'],
        ),
    ])
    def test_greasemonkey_duplicate_name(self, scripts_helper,
                                         header1, header2, expected_names):
        template = """
            // ==UserScript==
            {header}
            // ==/UserScript==
        """
        template = textwrap.dedent(template.lstrip('\n'))

        source1 = template.format(header="\n".join(header1))
        script1 = greasemonkey.GreasemonkeyScript.parse(source1)
        source2 = template.format(header="\n".join(header2))
        script2 = greasemonkey.GreasemonkeyScript.parse(source2)
        scripts_helper.inject([script1, script2])

        names = [script.name() for script in scripts_helper.get_scripts()]
        assert names == expected_names

        source3 = textwrap.dedent(template.lstrip('\n')).format(header="// @name other")
        script3 = greasemonkey.GreasemonkeyScript.parse(source3)
        scripts_helper.inject([script3])


class TestFindFlags:

    @pytest.mark.parametrize("case_sensitive, backward, expected", [
        (True, True, (QWebEnginePage.FindFlag.FindCaseSensitively |
                      QWebEnginePage.FindFlag.FindBackward)),
        (True, False, QWebEnginePage.FindFlag.FindCaseSensitively),
        (False, True, QWebEnginePage.FindFlag.FindBackward),
        (False, False, QWebEnginePage.FindFlag(0)),
    ])
    def test_to_qt(self, case_sensitive, backward, expected):
        flags = webenginetab._FindFlags(
            case_sensitive=case_sensitive,
            backward=backward,
        )
        assert flags.to_qt() == expected

    @pytest.mark.parametrize("case_sensitive, backward, expected", [
        (True, True, True),
        (True, False, True),
        (False, True, True),
        (False, False, False),
    ])
    def test_bool(self, case_sensitive, backward, expected):
        flags = webenginetab._FindFlags(
            case_sensitive=case_sensitive,
            backward=backward,
        )
        assert bool(flags) == expected

    @pytest.mark.parametrize("case_sensitive, backward, expected", [
        (True, True, "FindCaseSensitively|FindBackward"),
        (True, False, "FindCaseSensitively"),
        (False, True, "FindBackward"),
        (False, False, "<no find flags>"),
    ])
    def test_str(self, case_sensitive, backward, expected):
        flags = webenginetab._FindFlags(
            case_sensitive=case_sensitive,
            backward=backward,
        )
        assert str(flags) == expected


class TestWebEnginePermissions:

    def test_clipboard_value(self):
        # Ensure the ClipboardReadWrite permission is in the permission map,
        # despite us specifying it by number.
        permissions_cls = webenginetab._WebEnginePermissions
        try:
            clipboard = QWebEnginePage.Feature.ClipboardReadWrite
        except AttributeError:
            pytest.skip("enum member not available")
        assert clipboard in permissions_cls._options
        assert clipboard in permissions_cls._messages


class TestPageLifecycle:

    @pytest.fixture(autouse=True)
    def check_version(self):
        # While the lifecycle feature was introduced in 5.14, PyQt seems to
        # have trouble connecting to the signal we require on 6.4 and prior.
        # https://github.com/qutebrowser/qutebrowser/pull/8547#issuecomment-2890997662
        if versions.webengine < utils.VersionNumber(6, 5):
            pytest.skip("Lifecycle feature requires Webengine 6.5+")

    @pytest.fixture
    def set_state_mock(
        self,
        webengine_tab: webenginetab.WebEngineTab,
        monkeypatch,
        mocker,
    ):
        set_state_mock = mocker.Mock()
        monkeypatch.setattr(
            webengine_tab._widget.page(),
            "setLifecycleState",
            set_state_mock,
        )
        return set_state_mock

    @pytest.fixture(autouse=True)
    def set_config_defaults(
        self,
        config_stub,
        set_state_mock,
    ):
        self.set_config(config_stub)

    def set_config(
        self,
        config_stub,
        freeze_delay=0,
        discard_delay=0,
        enabled=True,
    ):
        config_stub.val.qt.chromium.lifecycle_state_freeze_delay = freeze_delay
        config_stub.val.qt.chromium.lifecycle_state_discard_delay = discard_delay
        config_stub.val.qt.chromium.use_recommended_page_lifecycle_state = enabled

    def test_qt_method_is_called(
        self,
        webengine_tab: webenginetab.WebEngineTab,
        set_state_mock,
        qtbot,
    ):
        """Basic test to show that we call QT after going through our code."""
        webengine_tab._on_recommended_state_changed(QWebEnginePage.LifecycleState.Discarded)
        with qtbot.wait_signal(webengine_tab._lifecycle_timer.timeout):
            pass
        set_state_mock.assert_called_once_with(QWebEnginePage.LifecycleState.Discarded)

    @pytest.mark.parametrize(
        "new_state, freeze_delay, discard_delay",
        [
            (QWebEnginePage.LifecycleState.Discarded, 2000, 10,),
            (QWebEnginePage.LifecycleState.Frozen, 10, 2000,),
        ]
    )
    def test_per_state_delay(
        self,
        webengine_tab: webenginetab.WebEngineTab,
        monkeypatch,
        mocker,
        set_state_mock,
        config_stub,
        qtbot,
        new_state,
        freeze_delay,
        discard_delay,
    ):
        """Show that a different time delay can get set for each state."""
        self.set_config(
            config_stub,
            freeze_delay=freeze_delay,
            discard_delay=discard_delay,
        )

        webengine_tab._on_recommended_state_changed(new_state)

        timer = webengine_tab._lifecycle_timer
        assert timer.remainingTime() == (
            freeze_delay
            if new_state == QWebEnginePage.LifecycleState.Frozen
            else discard_delay
        )

        with qtbot.wait_signal(timer.timeout, timeout=100):
            pass
        set_state_mock.assert_called_once_with(new_state)

    def test_state_disabled(
        self,
        webengine_tab: webenginetab.WebEngineTab,
        monkeypatch,
        config_stub,
    ):
        """For negative delay values, the timer shouldn't be scheduled."""
        self.set_config(
            config_stub,
            discard_delay=-1,
        )
        webengine_tab._on_recommended_state_changed(QWebEnginePage.LifecycleState.Discarded)
        assert not webengine_tab._lifecycle_timer.isActive()

    def test_pinned_tabs_untouched(
        self,
        webengine_tab: webenginetab.WebEngineTab,
        monkeypatch,
        config_stub,
    ):
        """Don't change lifecycle state for a pinned tab."""
        webengine_tab.set_pinned(True)
        webengine_tab._on_recommended_state_changed(QWebEnginePage.LifecycleState.Frozen)
        assert not webengine_tab._lifecycle_timer.isActive()

    def test_timer_interrupted(
        self,
        webengine_tab: webenginetab.WebEngineTab,
        set_state_mock,
        config_stub,
        qtbot,
    ):
        """Pending time should be cancelled when a new signal comes in."""
        self.set_config(
            config_stub,
            freeze_delay=1,
            discard_delay=3,
        )
        timer = webengine_tab._lifecycle_timer
        webengine_tab._on_recommended_state_changed(QWebEnginePage.LifecycleState.Frozen)
        assert timer.remainingTime() == 1

        webengine_tab._on_recommended_state_changed(QWebEnginePage.LifecycleState.Discarded)
        assert timer.remainingTime() == 3

        with qtbot.wait_signal(webengine_tab._lifecycle_timer.timeout):
            pass
        set_state_mock.assert_called_once_with(QWebEnginePage.LifecycleState.Discarded)
