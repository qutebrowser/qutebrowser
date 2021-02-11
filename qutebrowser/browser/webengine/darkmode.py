# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Get darkmode arguments to pass to Qt.

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

Qt 5.15.3
---------

Dark mode settings seem to be the same, but "prefers color scheme dark" changed enum
values.
"""

import os
import enum
from typing import (Any, Iterable, Iterator, Mapping, MutableMapping, Optional, Set,
                    Tuple, Union)

from qutebrowser.config import config
from qutebrowser.utils import usertypes, utils, log, version


class Variant(enum.Enum):

    """A dark mode variant."""

    qt_511_to_513 = enum.auto()
    qt_514 = enum.auto()
    qt_515_0 = enum.auto()
    qt_515_1 = enum.auto()
    qt_515_2 = enum.auto()
    qt_515_3 = enum.auto()


# Mapping from a colors.webpage.darkmode.algorithm setting value to
# Chromium's DarkModeInversionAlgorithm enum values.
_ALGORITHMS = {
    # 0: kOff (not exposed)
    # 1: kSimpleInvertForTesting (not exposed)
    'brightness-rgb': 2,  # kInvertBrightness
    'lightness-hsl': 3,  # kInvertLightness
    'lightness-cielab': 4,  # kInvertLightnessLAB
}
# kInvertLightnessLAB is not available with Qt < 5.14
_ALGORITHMS_BEFORE_QT_514 = _ALGORITHMS.copy()
_ALGORITHMS_BEFORE_QT_514['lightness-cielab'] = _ALGORITHMS['lightness-hsl']

# Mapping from a colors.webpage.darkmode.policy.images setting value to
# Chromium's DarkModeImagePolicy enum values.
_IMAGE_POLICIES = {
    'always': 0,  # kFilterAll
    'never': 1,  # kFilterNone
    'smart': 2,  # kFilterSmart
}

# Mapping from a colors.webpage.darkmode.policy.page setting value to
# Chromium's DarkModePagePolicy enum values.
_PAGE_POLICIES = {
    'always': 0,  # kFilterAll
    'smart': 1,  # kFilterByBackground
}

_BOOLS = {
    True: 'true',
    False: 'false',
}

_DarkModeSettingsType = Iterable[
    Tuple[
        str,  # qutebrowser option name
        str,  # darkmode setting name
        # Mapping from the config value to a string (or something convertible
        # to a string) which gets passed to Chromium.
        Optional[Mapping[Any, Union[str, int]]],
    ],
]

_DarkModeDefinitionType = Tuple[_DarkModeSettingsType, Set[str]]

# Our defaults for policy.images are different from Chromium's, so we mark it as
# mandatory setting - except on Qt 5.15.0 where we don't, so we don't get the
# workaround warning below if the setting wasn't explicitly customized.

_DARK_MODE_DEFINITIONS: MutableMapping[Variant, _DarkModeDefinitionType] = {
    Variant.qt_515_2: ([
        # 'darkMode' renamed to 'forceDarkMode'
        ('enabled', 'forceDarkModeEnabled', _BOOLS),
        ('algorithm', 'forceDarkModeInversionAlgorithm', _ALGORITHMS),

        ('policy.images', 'forceDarkModeImagePolicy', _IMAGE_POLICIES),
        ('contrast', 'forceDarkModeContrast', None),
        ('grayscale.all', 'forceDarkModeGrayscale', _BOOLS),

        ('policy.page', 'forceDarkModePagePolicy', _PAGE_POLICIES),
        ('threshold.text', 'forceDarkModeTextBrightnessThreshold', None),
        (
            'threshold.background',
            'forceDarkModeBackgroundBrightnessThreshold',
            None
        ),
        ('grayscale.images', 'forceDarkModeImageGrayscale', None),
    ], {'enabled', 'policy.images'}),

    Variant.qt_515_1: ([
        # 'policy.images' mandatory again
        ('enabled', 'darkModeEnabled', _BOOLS),
        ('algorithm', 'darkModeInversionAlgorithm', _ALGORITHMS),

        ('policy.images', 'darkModeImagePolicy', _IMAGE_POLICIES),
        ('contrast', 'darkModeContrast', None),
        ('grayscale.all', 'darkModeGrayscale', _BOOLS),

        ('policy.page', 'darkModePagePolicy', _PAGE_POLICIES),
        ('threshold.text', 'darkModeTextBrightnessThreshold', None),
        ('threshold.background', 'darkModeBackgroundBrightnessThreshold', None),
        ('grayscale.images', 'darkModeImageGrayscale', None),
    ], {'enabled', 'policy.images'}),

    Variant.qt_515_0: ([
        # 'policy.images' not mandatory because it's broken
        ('enabled', 'darkModeEnabled', _BOOLS),
        ('algorithm', 'darkModeInversionAlgorithm', _ALGORITHMS),

        ('policy.images', 'darkModeImagePolicy', _IMAGE_POLICIES),
        ('contrast', 'darkModeContrast', None),
        ('grayscale.all', 'darkModeGrayscale', _BOOLS),

        ('policy.page', 'darkModePagePolicy', _PAGE_POLICIES),
        ('threshold.text', 'darkModeTextBrightnessThreshold', None),
        ('threshold.background', 'darkModeBackgroundBrightnessThreshold', None),
        ('grayscale.images', 'darkModeImageGrayscale', None),
    ], {'enabled'}),

    Variant.qt_514: ([
        ('algorithm', 'darkMode', _ALGORITHMS),  # new: kInvertLightnessLAB

        ('policy.images', 'darkModeImagePolicy', _IMAGE_POLICIES),
        ('contrast', 'darkModeContrast', None),
        ('grayscale.all', 'darkModeGrayscale', _BOOLS),

        ('policy.page', 'darkModePagePolicy', _PAGE_POLICIES),
        ('threshold.text', 'darkModeTextBrightnessThreshold', None),
        ('threshold.background', 'darkModeBackgroundBrightnessThreshold', None),
        ('grayscale.images', 'darkModeImageGrayscale', None),
    ], {'algorithm', 'policy.images'}),

    Variant.qt_511_to_513: ([
        ('algorithm', 'highContrastMode', _ALGORITHMS_BEFORE_QT_514),

        ('policy.images', 'highContrastImagePolicy', _IMAGE_POLICIES),  # new: smart
        ('contrast', 'highContrastContrast', None),
        ('grayscale.all', 'highContrastGrayscale', _BOOLS),
    ], {'algorithm', 'policy.images'}),
}
_DARK_MODE_DEFINITIONS[Variant.qt_515_3] = _DARK_MODE_DEFINITIONS[Variant.qt_515_2]


def _variant() -> Variant:
    """Get the dark mode variant based on the underlying Qt version."""
    env_var = os.environ.get('QUTE_DARKMODE_VARIANT')
    if env_var is not None:
        try:
            return Variant[env_var]
        except KeyError:
            log.init.warning(f"Ignoring invalid QUTE_DARKMODE_VARIANT={env_var}")

    versions = version.qtwebengine_versions(avoid_init=True)
    if (versions.webengine == utils.VersionNumber(5, 15, 2) and
            versions.chromium is not None and
            versions.chromium.startswith('87.')):
        # WORKAROUND for Gentoo packaging something newer as 5.15.2...
        return Variant.qt_515_3
    elif versions.webengine >= utils.VersionNumber(5, 15, 2):
        return Variant.qt_515_2
    elif versions.webengine == utils.VersionNumber(5, 15, 1):
        return Variant.qt_515_1
    elif versions.webengine == utils.VersionNumber(5, 15):
        return Variant.qt_515_0
    elif versions.webengine >= utils.VersionNumber(5, 14):
        return Variant.qt_514
    elif versions.webengine >= utils.VersionNumber(5, 11):
        return Variant.qt_511_to_513
    raise utils.Unreachable(versions.webengine)


def settings() -> Iterator[Tuple[str, str]]:
    """Get necessary blink settings to configure dark mode for QtWebEngine."""
    variant = _variant()

    if config.val.colors.webpage.prefers_color_scheme_dark:
        if variant == Variant.qt_515_2:
            yield "preferredColorScheme", "1"
        elif variant == Variant.qt_515_3:
            # With Chromium 85 (> Qt 5.15.2), the enumeration has changed in Blink and
            # this will need to be set to '0' instead:
            # https://chromium-review.googlesource.com/c/chromium/src/+/2232922
            yield "preferredColorScheme", "0"
        # With older Qt versions, this is passed in qtargs.py as --force-dark-mode
        # instead.

    if not config.val.colors.webpage.darkmode.enabled:
        return

    setting_defs, mandatory_settings = _DARK_MODE_DEFINITIONS[variant]

    for setting, key, mapping in setting_defs:
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
                variant == Variant.qt_515_0):
            # WORKAROUND for
            # https://codereview.qt-project.org/c/qt/qtwebengine-chromium/+/304211
            log.init.warning("Ignoring colors.webpage.darkmode.policy.images = smart "
                             "because of Qt 5.15.0 bug")
            continue

        if mapping is not None:
            value = mapping[value]

        yield key, str(value)
