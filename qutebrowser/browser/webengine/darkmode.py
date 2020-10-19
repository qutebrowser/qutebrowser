# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Get darkmode arguments to pass to Qt."""

import enum
import typing

try:
    from PyQt5.QtWebEngine import PYQT_WEBENGINE_VERSION
except ImportError:  # pragma: no cover
    # Added in PyQt 5.13
    PYQT_WEBENGINE_VERSION = None  # type: ignore[assignment]

from qutebrowser.config import config
from qutebrowser.utils import usertypes, qtutils, utils, log


class Version(enum.Enum):

    unavailable = -1
    qt_510 = 0
    qt_511_to_513 = 1
    qt_514 = 2
    qt_515_0 = 3
    qt_515_1 = 4
    qt_515_2 = 5


def _version() -> Version:
    """Get the dark mode version based on the underlying Qt version."""
    if PYQT_WEBENGINE_VERSION is not None:
        # Available with Qt >= 5.13
        if PYQT_WEBENGINE_VERSION >= 0x050f02:
            return Version.qt_515_2
        elif PYQT_WEBENGINE_VERSION == 0x050f01:
            return Version.qt_515_1
        elif PYQT_WEBENGINE_VERSION == 0x050f00:
            return Version.qt_515_0
        elif PYQT_WEBENGINE_VERSION >= 0x050e00:
            return Version.qt_514
        elif PYQT_WEBENGINE_VERSION >= 0x050d00:
            return Version.qt_511_to_513
        raise utils.Unreachable(hex(PYQT_WEBENGINE_VERSION))

    # If we don't have PYQT_WEBENGINE_VERSION, we'll need to assume based on the Qt
    # version.
    assert not qtutils.version_check('5.13', compiled=False)  # type: ignore[unreachable]

    if qtutils.version_check('5.11', compiled=False):
        return Version.qt_511_to_513
    elif qtutils.version_check('5.10', compiled=False):
        return Version.qt_510

    return Version.unavailable


def settings() -> typing.Iterator[typing.Tuple[str, str]]:
    """Get necessary blink settings to configure dark mode for QtWebEngine.

    Overview of blink setting names based on the Qt version:

    Qt 5.10
    -------

    First implementation, called "high contrast mode".

    - highContrastMode (kOff/kSimpleInvertForTesting/kInvertBrightness/kInvertLightness)
    - highContrastGrayscale (bool)
    - highContrastContrast (float)
    - highContractImagePolicy (kFilterAll/kFilterNone)

    Qt 5.11, 5.12, 5.13
    -------------------

    New "smart" image policy.

    - Mode/Grayscale/Contrast as above
    - highContractImagePolicy (kFilterAll/kFilterNone/kFilterSmart [new!])

    Qt 5.14
    -------

    Renamed to "darkMode".

    - darkMode (kOff/kSimpleInvertForTesting/kInvertBrightness/kInvertLightness/
                kInvertLightnessLAB [new!])
    - darkModeGrayscale (bool)
    - darkModeContrast (float)
    - darkModeImagePolicy (kFilterAll/kFilterNone/kFilterSmart)
    - darkModePagePolicy (kFilterAll/kFilterByBackground) [new!]
    - darkModeTextBrightnessThreshold (int) [new!]
    - darkModeBackgroundBrightnessThreshold (int) [new!]
    - darkModeImageGrayscale (float) [new!]

    Qt 5.15.0 and 5.15.1
    --------------------

    "darkMode" split into "darkModeEnabled" and "darkModeInversionAlgorithm".

    - darkModeEnabled (bool) [new!]
    - darkModeInversionAlgorithm (kSimpleInvertForTesting/kInvertBrightness/
                                  kInvertLightness/kInvertLightnessLAB)
    - Rest (except darkMode) as above.
    - NOTE: smart image policy is broken with Qt 5.15.0!

    Qt 5.15.2
    ---------

    Prefix changed to "forceDarkMode".

    - As with Qt 5.15.0 / .1, but with "forceDarkMode" as prefix.
    """
    if not config.val.colors.webpage.darkmode.enabled:
        return

    # Mapping from a colors.webpage.darkmode.algorithm setting value to
    # Chromium's DarkModeInversionAlgorithm enum values.
    algorithms = {
        # 0: kOff (not exposed)
        # 1: kSimpleInvertForTesting (not exposed)
        'brightness-rgb': 2,  # kInvertBrightness
        'lightness-hsl': 3,  # kInvertLightness
        'lightness-cielab': 4,  # kInvertLightnessLAB
    }
    # kInvertLightnessLAB is not available with Qt < 5.14
    algorithms_before_qt_514 = algorithms.copy()
    algorithms_before_qt_514['lightness-cielab'] = algorithms['lightness-hsl']

    # Mapping from a colors.webpage.darkmode.policy.images setting value to
    # Chromium's DarkModeImagePolicy enum values.
    image_policies = {
        'always': 0,  # kFilterAll
        'never': 1,  # kFilterNone
        'smart': 2,  # kFilterSmart
    }
    # Image policy smart is not available with Qt 5.10
    image_policies_qt_510 = image_policies.copy()
    image_policies_qt_510['smart'] = image_policies['never']

    # Mapping from a colors.webpage.darkmode.policy.page setting value to
    # Chromium's DarkModePagePolicy enum values.
    page_policies = {
        'always': 0,  # kFilterAll
        'smart': 1,  # kFilterByBackground
    }

    bools = {
        True: 'true',
        False: 'false',
    }

    _setting_description_type = typing.Tuple[
        str,  # qutebrowser option name
        str,  # darkmode setting name
        # Mapping from the config value to a string (or something convertable
        # to a string) which gets passed to Chromium.
        typing.Optional[typing.Mapping[typing.Any, typing.Union[str, int]]],
    ]
    _dark_mode_definition_type = typing.Tuple[
        typing.Iterable[_setting_description_type],
        typing.Set[str],
    ]

    # Our defaults for policy.images are different from Chromium's, so we mark it as
    # mandatory setting - except on Qt 5.15.0 where we don't, so we don't get the
    # workaround warning below if the setting wasn't explicitly customized.

    version = _version()
    dark_mode_definitions = {
        Version.qt_515_2: ([
            # 'darkMode' renamed to 'forceDarkMode'
            ('enabled', 'forceDarkModeEnabled', bools),
            ('algorithm', 'forceDarkModeInversionAlgorithm', algorithms),

            ('policy.images', 'forceDarkModeImagePolicy', image_policies),
            ('contrast', 'forceDarkModeContrast', None),
            ('grayscale.all', 'forceDarkModeGrayscale', bools),

            ('policy.page', 'forceDarkModePagePolicy', page_policies),
            ('threshold.text', 'forceDarkModeTextBrightnessThreshold', None),
            (
                'threshold.background',
                'forceDarkModeBackgroundBrightnessThreshold',
                None
            ),
            ('grayscale.images', 'forceDarkModeImageGrayscale', None),
        ], {'enabled', 'policy.images'}),

        Version.qt_515_1: ([
            # 'policy.images' mandatory again
            ('enabled', 'darkModeEnabled', bools),
            ('algorithm', 'darkModeInversionAlgorithm', algorithms),

            ('policy.images', 'darkModeImagePolicy', image_policies),
            ('contrast', 'darkModeContrast', None),
            ('grayscale.all', 'darkModeGrayscale', bools),

            ('policy.page', 'darkModePagePolicy', page_policies),
            ('threshold.text', 'darkModeTextBrightnessThreshold', None),
            ('threshold.background', 'darkModeBackgroundBrightnessThreshold', None),
            ('grayscale.images', 'darkModeImageGrayscale', None),
        ], {'enabled', 'policy.images'}),

        Version.qt_515_0: ([
            # 'policy.images' not mandatory because it's broken
            ('enabled', 'darkModeEnabled', bools),
            ('algorithm', 'darkModeInversionAlgorithm', algorithms),

            ('policy.images', 'darkModeImagePolicy', image_policies),
            ('contrast', 'darkModeContrast', None),
            ('grayscale.all', 'darkModeGrayscale', bools),

            ('policy.page', 'darkModePagePolicy', page_policies),
            ('threshold.text', 'darkModeTextBrightnessThreshold', None),
            ('threshold.background', 'darkModeBackgroundBrightnessThreshold', None),
            ('grayscale.images', 'darkModeImageGrayscale', None),
        ], {'enabled'}),

        Version.qt_514: ([
            ('algorithm', 'darkMode', algorithms),  # new: kInvertLightnessLAB

            ('policy.images', 'darkModeImagePolicy', image_policies),
            ('contrast', 'darkModeContrast', None),
            ('grayscale.all', 'darkModeGrayscale', bools),

            # New
            ('policy.page', 'darkModePagePolicy', page_policies),
            ('threshold.text', 'darkModeTextBrightnessThreshold', None),
            ('threshold.background', 'darkModeBackgroundBrightnessThreshold', None),
            ('grayscale.images', 'darkModeImageGrayscale', None),
        ], {'algorithm', 'policy.images'}),

        Version.qt_511_to_513: ([
            ('algorithm', 'highContrastMode', algorithms_before_qt_514),

            ('policy.images', 'highContrastImagePolicy', image_policies),  # new: smart
            ('contrast', 'highContrastContrast', None),
            ('grayscale.all', 'highContrastGrayscale', bools),
        ], {'algorithm', 'policy.images'}),

        Version.qt_510: ([
            ('algorithm', 'highContrastMode', algorithms_before_qt_514),

            ('policy.images', 'highContrastImagePolicy', image_policies_qt_510),
            ('contrast', 'highContrastContrast', None),
            ('grayscale.all', 'highContrastGrayscale', bools),
        ], {'algorithm'}),
    }  # type: typing.Mapping[Version, _dark_mode_definition_type]

    settings, mandatory_settings = dark_mode_definitions[version]

    for setting, key, mapping in settings:
        # To avoid blowing up the commandline length, we only pass modified
        # settings to Chromium, as our defaults line up with Chromium's.
        # However, we always pass enabled/algorithm to make sure dark mode gets
        # actually turned on.
        value = config.instance.get(
            'colors.webpage.darkmode.' + setting,
            fallback=setting in mandatory_settings)
        if isinstance(value, usertypes.Unset):
            continue

        if (setting == 'policy.images' and value == 'smart' and
                version == Version.qt_515_0):
            # WORKAROUND for
            # https://codereview.qt-project.org/c/qt/qtwebengine-chromium/+/304211
            log.init.warning("Ignoring colors.webpage.darkmode.policy.images = smart "
                             "because of Qt 5.15.0 bug")
            continue

        if mapping is not None:
            value = mapping[value]

        yield key, str(value)
