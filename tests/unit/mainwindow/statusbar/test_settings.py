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

"""Test statusbar settings widget."""

from unittest import mock

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.mainwindow.statusbar import settings
from qutebrowser.config import configtypes


CONFIG_OPTION = settings.BooleanSettings.config_option


class TestData:
    """Common data used for initing config_stub and making assertions about."""

    config = {
        'content.webgl': 'G',
        'content.images': 'I',
        'content.geolocation': 'L',
        'content.javascript.enabled': 'Y',
    }

    @property
    def setting(self):
        """This data as it would appear in the config setting."""
        return ['|'.join(x) for x in self.config]


@pytest.fixture()
def no_winreg(monkeypatch):
    """Mock out the only function that relies on windows and tabs existing."""
    monkeypatch.setattr(settings.BooleanSettings, '_current_tab',
                        mock.Mock(return_value=None))


@pytest.fixture()
def with_tab(web_tab, tabbed_browser_stubs):
    """Set up the window registry with two windows and a full tab."""
    tabbed_browser = tabbed_browser_stubs[0]
    tabbed_browser.widget.current_index = 1
    tabbed_browser.widget.tabs = [web_tab]
    yield tabbed_browser


@pytest.fixture()
def data(config_stub):
    """Init config_stub to a known state and return data for asserts."""
    data = TestData()
    config_stub.set_obj(
        CONFIG_OPTION,
        data.config,
    )
    for setting_name in data.config:
        config_stub.set_obj(setting_name, True)
    yield data


def test_setting_is_parsed_on_init(qtbot, monkeypatch, data):
    """Test the config string is parsed at init time."""
    parse_mock = mock.Mock()
    monkeypatch.setattr(settings.BooleanSettings, '_parse_config', parse_mock)
    settings.BooleanSettings(None, 0)
    assert parse_mock.call_count == 1


def test_setting_can_be_correctly_parsed(qtbot, no_winreg, data):
    """Test the config string is parsed to the expected structure."""
    uut = settings.BooleanSettings(None, 0)
    assert uut._config == data.config


@pytest.mark.parametrize("setting_name, expect_change", [
    (CONFIG_OPTION, True),
    ("other.setting", False),
])
def test_settings_are_reparsed_on_config_change(
        qtbot, config_stub, monkeypatch, data, setting_name, expect_change
):
    """Make sure the config is updated when the relevant setting is."""
    parse_mock = mock.Mock()
    monkeypatch.setattr(settings.BooleanSettings, '_parse_config', parse_mock)
    uut = settings.BooleanSettings(None, 0)
    parse_mock.reset_mock()

    uut.on_config_changed(setting_name)
    if expect_change:
        assert parse_mock.call_count == 1
    else:
        assert parse_mock.call_count == 0


def test_changed_setting_is_handled(qtbot, config_stub, no_winreg, data):
    """Make sure changes in the setting are reflect in the internal config."""
    uut = settings.BooleanSettings(None, 0)
    assert uut._config == data.config

    to = {"content.images": "foo"}
    config_stub.set_obj(CONFIG_OPTION, to)
    uut._parse_config()
    assert uut._config != data.config


@pytest.mark.parametrize("with_webgl, expected", [
    (True, '[GILY]'),
    (False, '[ILY]'),
])
def test_text_matches_config(qtbot, data, no_winreg, monkeypatch,
                             with_webgl, expected):
    """Test the widget text is what we expect given the config."""
    bool_mock = mock.Mock()
    text_mock = mock.Mock()
    uut = settings.BooleanSettings(None, 0)
    monkeypatch.setattr(uut, '_to_bool', bool_mock)
    monkeypatch.setattr(uut, 'setText', text_mock)
    bool_mock.side_effect = [
        with_webgl,
        True, True, True,
    ]

    uut.on_url_changed(QUrl(''))
    text_mock.assert_called_once()
    actual = text_mock.call_args[0][0]
    # Py3.5- has different ordering than 3.6+
    assert sorted(actual) == sorted(expected)


@pytest.mark.parametrize("supports_pattern, expect_none", [
    (True, False),
    (False, True),
])
def test_setting_casting_handles_url_patterns(
        qtbot, data, no_winreg, monkeypatch, config_stub,
        supports_pattern, expect_none
):
    """Test we provide a url only for options that support it."""
    uut = settings.BooleanSettings(None, 0)
    get_obj_mock = mock.Mock()
    get_opt_mock = mock.Mock()
    get_opt_mock.return_value.supports_pattern = supports_pattern
    get_opt_mock.return_value.typ = configtypes.Bool()
    monkeypatch.setattr(config_stub, 'get_opt', get_opt_mock)
    monkeypatch.setattr(config_stub, 'get_obj', get_obj_mock)

    url = QUrl('http://example.com/')
    uut._to_bool('foobar', url)
    get_obj_mock.assert_called_once_with(
        'foobar',
        url=None if expect_none else url
    )


def test_setting_casting_ask_defers_to_tab(
        qtbot, data, no_winreg, monkeypatch, config_stub,
):
    """Test that we check permissions from the tab for BoolAsks."""
    test_feature_mock = mock.Mock()
    monkeypatch.setattr(settings.BooleanSettings, '_test_feature',
                        test_feature_mock)
    uut = settings.BooleanSettings(None, 0)
    test_feature_mock.reset_mock()
    get_obj_mock = mock.Mock(return_value='ask')
    get_opt_mock = mock.Mock()
    get_opt_mock.return_value.typ = configtypes.BoolAsk()
    monkeypatch.setattr(config_stub, 'get_opt', get_opt_mock)
    monkeypatch.setattr(config_stub, 'get_obj', get_obj_mock)

    uut._to_bool('foobar', QUrl(''))
    test_feature_mock.assert_called_once_with('foobar')


def test_integration(fake_statusbar, with_tab, monkeypatch, data):
    """Test everything works while hitting a real tab.

    Basically an integration test, requires graphics."""
    uut = settings.BooleanSettings(fake_statusbar, 0)
    expected = "[{}]".format(''.join(t[1] for t in data.config.items()))
    assert uut.text() == expected
