# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

import logging

import pytest

from qutebrowser.config import configdata
from qutebrowser.utils import usertypes, version
from qutebrowser.browser.webengine import darkmode
from qutebrowser.misc import objects
from helpers import utils


@pytest.fixture(autouse=True)
def patch_backend(monkeypatch):
    monkeypatch.setattr(objects, 'backend', usertypes.Backend.QtWebEngine)


@pytest.mark.parametrize('qversion, enabled, expected', [
    # Disabled or nothing set
    ("5.14", False, []),
    ("5.15.0", False, []),
    ("5.15.1", False, []),
    ("5.15.2", False, []),

    # Enabled in configuration
    ("5.14", True, []),
    ("5.15.0", True, []),
    ("5.15.1", True, []),
    ("5.15.2", True, [("preferredColorScheme", "1")]),
])
@utils.qt514
def test_colorscheme(config_stub, monkeypatch, qversion, enabled, expected):
    monkeypatch.setattr(darkmode.qtutils, 'qVersion', lambda: qversion)
    config_stub.val.colors.webpage.prefers_color_scheme_dark = enabled
    assert list(darkmode.settings()) == expected


@pytest.mark.parametrize('settings, expected', [
    # Disabled
    ({}, []),

    # Enabled without customization
    ({'enabled': True}, [('forceDarkModeEnabled', 'true')]),

    # Algorithm
    (
        {'enabled': True, 'algorithm': 'brightness-rgb'},
        [
            ('forceDarkModeEnabled', 'true'),
            ('forceDarkModeInversionAlgorithm', '2')
        ],
    ),
])
def test_basics(config_stub, monkeypatch, settings, expected):
    for k, v in settings.items():
        config_stub.set_obj('colors.webpage.darkmode.' + k, v)
    monkeypatch.setattr(darkmode, '_variant',
                        lambda: darkmode.Variant.qt_515_2)

    if expected:
        expected.append(('forceDarkModeImagePolicy', '2'))

    assert list(darkmode.settings()) == expected


QT_514_SETTINGS = [
    ('darkMode', '2'),
    ('darkModeImagePolicy', '2'),
    ('darkModeGrayscale', 'true'),
]


QT_515_0_SETTINGS = [
    ('darkModeEnabled', 'true'),
    ('darkModeInversionAlgorithm', '2'),
    ('darkModeGrayscale', 'true'),
]


QT_515_1_SETTINGS = [
    ('darkModeEnabled', 'true'),
    ('darkModeInversionAlgorithm', '2'),
    ('darkModeImagePolicy', '2'),
    ('darkModeGrayscale', 'true'),
]


QT_515_2_SETTINGS = [
    ('forceDarkModeEnabled', 'true'),
    ('forceDarkModeInversionAlgorithm', '2'),
    ('forceDarkModeImagePolicy', '2'),
    ('forceDarkModeGrayscale', 'true'),
]


@pytest.mark.parametrize('qversion, expected', [
    ('5.14.0', QT_514_SETTINGS),
    ('5.14.1', QT_514_SETTINGS),
    ('5.14.2', QT_514_SETTINGS),

    ('5.15.0', QT_515_0_SETTINGS),
    ('5.15.1', QT_515_1_SETTINGS),

    ('5.15.2', QT_515_2_SETTINGS),
])
def test_qt_version_differences(config_stub, monkeypatch, qversion, expected):
    monkeypatch.setattr(darkmode.qtutils, 'qVersion', lambda: qversion)

    major, minor, patch = [int(part) for part in qversion.split('.')]
    hexversion = major << 16 | minor << 8 | patch
    if major > 5 or minor >= 13:
        # Added in Qt 5.13
        monkeypatch.setattr(darkmode, 'PYQT_WEBENGINE_VERSION', hexversion)

    settings = {
        'enabled': True,
        'algorithm': 'brightness-rgb',
        'grayscale.all': True,
    }
    for k, v in settings.items():
        config_stub.set_obj('colors.webpage.darkmode.' + k, v)

    assert list(darkmode.settings()) == expected


@utils.qt514
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
def test_customization(config_stub, monkeypatch, setting, value, exp_key, exp_val):
    config_stub.val.colors.webpage.darkmode.enabled = True
    config_stub.set_obj('colors.webpage.darkmode.' + setting, value)
    monkeypatch.setattr(darkmode, '_variant', lambda: darkmode.Variant.qt_515_2)

    expected = []
    expected.append(('forceDarkModeEnabled', 'true'))
    if exp_key != 'ImagePolicy':
        expected.append(('forceDarkModeImagePolicy', '2'))
    expected.append(('forceDarkMode' + exp_key, exp_val))

    assert list(darkmode.settings()) == expected


@pytest.mark.parametrize('qversion, webengine_version, expected', [
    # Without PYQT_WEBENGINE_VERSION
    ('5.12.9', None, darkmode.Variant.qt_511_to_513),

    # With PYQT_WEBENGINE_VERSION
    (None, 0x050d00, darkmode.Variant.qt_511_to_513),
    (None, 0x050e00, darkmode.Variant.qt_514),
    (None, 0x050f00, darkmode.Variant.qt_515_0),
    (None, 0x050f01, darkmode.Variant.qt_515_1),
    (None, 0x050f02, darkmode.Variant.qt_515_2),
    (None, 0x060000, darkmode.Variant.qt_515_2),  # Qt 6
])
def test_variant(monkeypatch, qversion, webengine_version, expected):
    monkeypatch.setattr(darkmode.qtutils, 'qVersion', lambda: qversion)
    monkeypatch.setattr(darkmode, 'PYQT_WEBENGINE_VERSION', webengine_version)
    assert darkmode._variant() == expected


@pytest.mark.parametrize('value, is_valid, expected', [
    ('invalid_value', False, darkmode.Variant.qt_515_0),
    ('qt_515_2', True, darkmode.Variant.qt_515_2),
])
def test_variant_override(monkeypatch, caplog, value, is_valid, expected):
    monkeypatch.setattr(darkmode.qtutils, 'qVersion', lambda: None)
    monkeypatch.setattr(darkmode, 'PYQT_WEBENGINE_VERSION', 0x050f00)
    monkeypatch.setenv('QUTE_DARKMODE_VARIANT', value)

    with caplog.at_level(logging.WARNING):
        assert darkmode._variant() == expected

    log_msg = 'Ignoring invalid QUTE_DARKMODE_VARIANT=invalid_value'
    assert (log_msg in caplog.messages) != is_valid


def test_broken_smart_images_policy(config_stub, monkeypatch, caplog):
    config_stub.val.colors.webpage.darkmode.enabled = True
    config_stub.val.colors.webpage.darkmode.policy.images = 'smart'
    monkeypatch.setattr(darkmode, 'PYQT_WEBENGINE_VERSION', 0x050f00)

    with caplog.at_level(logging.WARNING):
        settings = list(darkmode.settings())

    assert caplog.messages[-1] == (
        'Ignoring colors.webpage.darkmode.policy.images = smart because of '
        'Qt 5.15.0 bug')

    expected = [
        [('darkModeEnabled', 'true')],  # Qt 5.15
        [('darkMode', '4')],  # Qt 5.14
    ]
    assert settings in expected


def test_new_chromium():
    """Fail if we encounter an unknown Chromium version.

    Dark mode in Chromium (or rather, the underlying Blink) is being changed with
    almost every Chromium release.

    Make this test fail deliberately with newer Chromium versions, so that
    we can test whether dark mode still works manually, and adjust if not.
    """
    assert version._chromium_version() in [
        'unavailable',  # QtWebKit
        '61.0.3163.140',  # Qt 5.10
        '65.0.3325.230',  # Qt 5.11
        '69.0.3497.128',  # Qt 5.12
        '73.0.3683.105',  # Qt 5.13
        '77.0.3865.129',  # Qt 5.14
        '80.0.3987.163',  # Qt 5.15.0
        '83.0.4103.122',  # Qt 5.15.2
    ]


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
            assert opt.raw_backends['QtWebEngine'] == 'Qt 5.14', name
