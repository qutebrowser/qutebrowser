# Copyright 2020-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

import logging

import pytest

from qutebrowser.config import configdata
from qutebrowser.utils import usertypes, version, utils
from qutebrowser.browser.webengine import darkmode
from qutebrowser.misc import objects


@pytest.fixture(autouse=True)
def patch_backend(monkeypatch):
    monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebEngine)


@pytest.fixture
def gentoo_versions():
    return version.WebEngineVersions(
        webengine=utils.VersionNumber(5, 15, 2),
        chromium='87.0.4280.144',
        source='faked',
    )


@pytest.mark.parametrize('value, webengine_version, expected', [
    # Auto
    ("auto", "5.15.2", [("preferredColorScheme", "2")]),  # QTBUG-89753
    ("auto", "5.15.3", []),
    ("auto", "6.2.0", []),

    # Unset
    (None, "5.15.2", [("preferredColorScheme", "2")]),  # QTBUG-89753
    (None, "5.15.3", []),
    (None, "6.2.0", []),

    # Dark
    ("dark", "5.15.2", [("preferredColorScheme", "1")]),
    ("dark", "5.15.3", [("preferredColorScheme", "0")]),
    ("dark", "6.2.0", [("preferredColorScheme", "0")]),

    # Light
    ("light", "5.15.2", [("preferredColorScheme", "2")]),
    ("light", "5.15.3", [("preferredColorScheme", "1")]),
    ("light", "6.2.0", [("preferredColorScheme", "1")]),
])
def test_colorscheme(config_stub, value, webengine_version, expected):
    versions = version.WebEngineVersions.from_pyqt(webengine_version)
    if value is not None:
        config_stub.val.colors.webpage.preferred_color_scheme = value

    darkmode_settings = darkmode.settings(versions=versions, special_flags=[])
    assert darkmode_settings['blink-settings'] == expected


def test_colorscheme_gentoo_workaround(config_stub, gentoo_versions):
    config_stub.val.colors.webpage.preferred_color_scheme = "dark"
    darkmode_settings = darkmode.settings(versions=gentoo_versions, special_flags=[])
    assert darkmode_settings['blink-settings'] == [("preferredColorScheme", "0")]


@pytest.mark.parametrize('settings, expected', [
    # Disabled
    ({}, [('preferredColorScheme', '2')]),

    # Enabled without customization
    (
        {'enabled': True},
        [
            ('preferredColorScheme', '2'),
            ('forceDarkModeEnabled', 'true'),
            ('forceDarkModeImagePolicy', '2'),
        ]
    ),

    # Algorithm
    (
        {'enabled': True, 'algorithm': 'brightness-rgb'},
        [
            ('preferredColorScheme', '2'),
            ('forceDarkModeEnabled', 'true'),
            ('forceDarkModeInversionAlgorithm', '2'),
            ('forceDarkModeImagePolicy', '2'),
        ],
    ),
])
def test_basics(config_stub, settings, expected):
    for k, v in settings.items():
        config_stub.set_obj('colors.webpage.darkmode.' + k, v)

    # Using Qt 5.15.2 because it has the least special cases.
    versions = version.WebEngineVersions.from_pyqt('5.15.2')
    darkmode_settings = darkmode.settings(versions=versions, special_flags=[])
    assert darkmode_settings['blink-settings'] == expected


QT_515_2_SETTINGS = {'blink-settings': [
    ('preferredColorScheme', '2'),  # QTBUG-89753
    ('forceDarkModeEnabled', 'true'),
    ('forceDarkModeInversionAlgorithm', '2'),
    ('forceDarkModeImagePolicy', '2'),
    ('forceDarkModeGrayscale', 'true'),
]}


QT_515_3_SETTINGS = {
    'blink-settings': [('forceDarkModeEnabled', 'true')],
    'dark-mode-settings': [
        ('InversionAlgorithm', '1'),
        ('ImagePolicy', '2'),
        ('IsGrayScale', 'true'),
    ],
}


@pytest.mark.parametrize('qversion, expected', [
    ('5.15.2', QT_515_2_SETTINGS),
    ('5.15.3', QT_515_3_SETTINGS),
])
def test_qt_version_differences(config_stub, qversion, expected):
    settings = {
        'enabled': True,
        'algorithm': 'brightness-rgb',
        'grayscale.all': True,
    }
    for k, v in settings.items():
        config_stub.set_obj('colors.webpage.darkmode.' + k, v)

    versions = version.WebEngineVersions.from_pyqt(qversion)
    darkmode_settings = darkmode.settings(versions=versions, special_flags=[])
    assert darkmode_settings == expected


@pytest.mark.parametrize('setting, value, exp_key, exp_val', [
    ('contrast', -0.5,
     'Contrast', '-0.5'),
    ('policy.page', 'smart',
     'PagePolicy', '1'),
    ('policy.images', 'smart',
     'ImagePolicy', '2'),
    ('threshold.text', 100,
     'TextBrightnessThreshold', '100'),
    ('threshold.background', 100,
     'BackgroundBrightnessThreshold', '100'),
    ('grayscale.all', True,
     'Grayscale', 'true'),
    ('grayscale.images', 0.5,
     'ImageGrayscale', '0.5'),
])
def test_customization(config_stub, setting, value, exp_key, exp_val):
    config_stub.val.colors.webpage.darkmode.enabled = True
    config_stub.set_obj('colors.webpage.darkmode.' + setting, value)

    expected = [
        ('preferredColorScheme', '2'),
        ('forceDarkModeEnabled', 'true'),
    ]
    if exp_key != 'ImagePolicy':
        expected.append(('forceDarkModeImagePolicy', '2'))
    expected.append(('forceDarkMode' + exp_key, exp_val))

    versions = version.WebEngineVersions.from_pyqt('5.15.2')
    darkmode_settings = darkmode.settings(versions=versions, special_flags=[])
    assert darkmode_settings['blink-settings'] == expected


@pytest.mark.parametrize('webengine_version, expected', [
    ('5.15.2', darkmode.Variant.qt_515_2),
    ('5.15.3', darkmode.Variant.qt_515_3),
    ('6.2.0', darkmode.Variant.qt_515_3),
])
def test_variant(webengine_version, expected):
    versions = version.WebEngineVersions.from_pyqt(webengine_version)
    assert darkmode._variant(versions) == expected


def test_variant_gentoo_workaround(gentoo_versions):
    assert darkmode._variant(gentoo_versions) == darkmode.Variant.qt_515_3


@pytest.mark.parametrize('value, is_valid, expected', [
    ('invalid_value', False, darkmode.Variant.qt_515_3),
    ('qt_515_2', True, darkmode.Variant.qt_515_2),
])
def test_variant_override(monkeypatch, caplog, value, is_valid, expected):
    versions = version.WebEngineVersions.from_pyqt('5.15.3')
    monkeypatch.setenv('QUTE_DARKMODE_VARIANT', value)

    with caplog.at_level(logging.WARNING):
        assert darkmode._variant(versions) == expected

    log_msg = 'Ignoring invalid QUTE_DARKMODE_VARIANT=invalid_value'
    assert (log_msg in caplog.messages) != is_valid


@pytest.mark.parametrize('flag, expected', [
    ('--blink-settings=key=value', [('key', 'value')]),
    ('--blink-settings=key=equal=rights', [('key', 'equal=rights')]),
    ('--blink-settings=one=1,two=2', [('one', '1'), ('two', '2')]),
    ('--enable-features=feat', []),
])
def test_pass_through_existing_settings(config_stub, flag, expected):
    config_stub.val.colors.webpage.darkmode.enabled = True
    versions = version.WebEngineVersions.from_pyqt('5.15.2')
    settings = darkmode.settings(versions=versions, special_flags=[flag])

    dark_mode_expected = [
        ('preferredColorScheme', '2'),
        ('forceDarkModeEnabled', 'true'),
        ('forceDarkModeImagePolicy', '2'),
    ]
    assert settings['blink-settings'] == expected + dark_mode_expected


def test_options(configdata_init):
    """Make sure all darkmode options have the right attributes set."""
    for name, opt in configdata.DATA.items():
        if not name.startswith('colors.webpage.darkmode.'):
            continue

        assert not opt.supports_pattern, name
        assert opt.restart, name

        if opt.backends:
            # On older Qt versions, this is an empty list.
            assert opt.backends == [usertypes.Backend.QtWebEngine], name

        if opt.raw_backends is not None:
            assert not opt.raw_backends['QtWebKit'], name
