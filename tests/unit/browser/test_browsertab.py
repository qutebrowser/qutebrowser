# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from unittest import mock

from qutebrowser.qt.core import QUrl
from qutebrowser.browser import browsertab


class TestAction:

    def test_run_string_valid(self, qtbot, web_tab):
        url_1 = QUrl("qute://testdata/data/backforward/1.txt")
        url_2 = QUrl("qute://testdata/data/backforward/2.txt")

        with qtbot.wait_signal(web_tab.load_finished):
            web_tab.load_url(url_1)
        with qtbot.wait_signal(web_tab.load_finished):
            web_tab.load_url(url_2)

        assert web_tab.url() == url_2
        with qtbot.wait_signal(web_tab.load_finished):
            web_tab.action.run_string("Back")
        assert web_tab.url() == url_1

    @pytest.mark.parametrize("member", ["blah", "PermissionUnknown"])
    def test_run_string_invalid(self, qtbot, web_tab, member):
        with pytest.raises(
            browsertab.WebTabError,
            match=f"{member} is not a valid web action!",
        ):
            web_tab.action.run_string(member)


class TestTestFeature:
    """Test the implementations of AbstractTab.test_feature()."""

    # common permission implemented across all backend versions
    setting = "content.geolocation"

    @pytest.mark.parametrize("url", [
        (None),
        ("https://invalid.com/"),
        ("https://example.com/"),
    ])
    def test_calls_config_right(self, web_tab, config_stub, monkeypatch,
                                url):
        """Check call to config given current url and passed arg."""
        config_get_stub = mock.Mock(return_value=browsertab.FeatureState.granted)
        monkeypatch.setattr(config_stub, 'get', config_get_stub)

        url = QUrl(url) if url else None
        monkeypatch.setattr(web_tab, 'url', mock.Mock(return_value=url))

        web_tab.permissions.test_feature(self.setting)

        config_get_stub.assert_called_once_with(self.setting, url=url)

    @pytest.mark.parametrize("value, expect", [
        ("ask", "ask"),
        (True, True),
        (False, False),
    ])
    def test_returns_expected_value(self, web_tab, config_stub, monkeypatch,
                                    value, expect):
        """Make sure the response from config.get is interpreted right."""
        monkeypatch.setattr(config_stub, 'get', mock.Mock(return_value=value))
        monkeypatch.setattr(web_tab, 'url', mock.Mock(return_value=None))

        ret = web_tab.permissions.test_feature(self.setting)

        assert ret.value == expect

    def test_error_on_unknown_setting_name(self, web_tab):
        with pytest.raises(browsertab.WebTabError):
            web_tab.permissions.test_feature('not.a.real.thing')

    @pytest.mark.parametrize("setting, granted, expect", [
        ("ask", False, False),
        ("ask", True, True),
        ("ask", None, "ask"),
        (True, True, True),
        (True, False, False),
        (True, None, True),
        (False, True, True),
        (False, False, False),
        (False, None, False),
    ])
    def test_page_state_is_reported(self, web_tab, config_stub, monkeypatch,
                                    setting, granted, expect):
        """Ensure that what has been granted to a page is reported.

        As opposed to what the setting is configured as. For example if a
        setting is set to true, a page requests access and then the user
        changes the setting to false or ask, True should still be reported.
        """
        monkeypatch.setattr(web_tab, 'url', mock.Mock(return_value=None))
        config_get_stub = mock.Mock(return_value=setting)
        monkeypatch.setattr(config_stub, 'get', config_get_stub)

        features = {
            1: browsertab.Feature(
                self.setting,
                "plz?",
                granted if granted is None else browsertab.FeatureState(granted)
            )
        }

        monkeypatch.setattr(web_tab.permissions, 'features', features)

        assert web_tab.permissions.test_feature(self.setting).value == expect
