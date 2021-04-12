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

Settings split to new --dark-mode-settings switch:
https://chromium-review.googlesource.com/c/chromium/src/+/2390588

- Everything except forceDarkModeEnabled goes to the other switch.
- Algorithm uses a different enum with kOff gone.
- No "forceDarkMode" prefix anymore.

Removed DarkModePagePolicy:
https://chromium-review.googlesource.com/c/chromium/src/+/2323441

"prefers color scheme dark" changed enum values:
https://chromium-review.googlesource.com/c/chromium/src/+/2232922

- Now needs to be 0 for dark and 1 for light
  (before: 0 no preference / 1 dark / 2 light)
"""

import os
import copy
import enum
import dataclasses
import collections
from typing import (Any, Iterator, Mapping, MutableMapping, Optional, Set, Tuple, Union,
                    Sequence, List)

from qutebrowser.config import config
from qutebrowser.utils import usertypes, utils, log, version


_BLINK_SETTINGS = 'blink-settings'


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
# Qt >= 5.15.3, based on dark_mode_settings.h
_ALGORITHMS_NEW = {
    # 0: kSimpleInvertForTesting (not exposed)
    'brightness-rgb': 1,  # kInvertBrightness
    'lightness-hsl': 2,  # kInvertLightness
    'lightness-cielab': 3,  # kInvertLightnessLAB
}

# Mapping from a colors.webpage.darkmode.policy.images setting value to
# Chromium's DarkModeImagePolicy enum values.
# Values line up with dark_mode_settings.h for 5.15.3+.
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


@dataclasses.dataclass
class _Setting:

    """A single dark mode setting."""

    option: str
    chromium_key: str
    mapping: Optional[Mapping[Any, Union[str, int]]] = None

    def _value_str(self, value: Any) -> str:
        if self.mapping is None:
            return str(value)
        return str(self.mapping[value])

    def chromium_tuple(self, value: Any) -> Tuple[str, str]:
        return self.chromium_key, self._value_str(value)

    def with_prefix(self, prefix: str) -> '_Setting':
        return _Setting(
            option=self.option,
            chromium_key=prefix + self.chromium_key,
            mapping=self.mapping,
        )


class _Definition:

    """A collection of dark mode setting names for the given QtWebEngine version.

    Attributes:
        _settings: A list of _Setting objects for this definition.
        mandatory: A set of settings which should always be passed to Chromium, even if
                   not customized from the default.
        prefix: A string prefix to add to all Chromium setting names.
        switch_names: A dict mapping option names to the Chromium switch they belong to.
                      None is used as fallback key, i.e. for settings not in the dict.
    """

    def __init__(
            self,
            *args: _Setting,
            mandatory: Set[str],
            prefix: str,
            switch_names: Mapping[Optional[str], str] = None,
    ) -> None:
        self._settings = args
        self.mandatory = mandatory
        self.prefix = prefix

        if switch_names is not None:
            self._switch_names = switch_names
        else:
            self._switch_names = {None: _BLINK_SETTINGS}

    def prefixed_settings(self) -> Iterator[Tuple[str, _Setting]]:
        """Get all "prepared" settings.

        Yields tuples which contain the Chromium setting key (e.g. 'blink-settings' or
        'dark-mode-settings') and the corresponding _Settings object.
        """
        for setting in self._settings:
            switch = self._switch_names.get(setting.option, self._switch_names[None])
            yield switch, setting.with_prefix(self.prefix)

    def copy_with(self, attr: str, value: Any) -> '_Definition':
        """Get a new _Definition object with a changed attribute.

        NOTE: This does *not* copy the settings list. Both objects will reference the
        same list.
        """
        new = copy.copy(self)
        setattr(new, attr, value)
        return new


# Our defaults for policy.images are different from Chromium's, so we mark it as
# mandatory setting - except on Qt 5.15.0 where we don't, so we don't get the
# workaround warning below if the setting wasn't explicitly customized.

_DEFINITIONS: MutableMapping[Variant, _Definition] = {
    Variant.qt_515_3: _Definition(
        # Different switch for settings
        _Setting('enabled', 'forceDarkModeEnabled', _BOOLS),
        _Setting('algorithm', 'InversionAlgorithm', _ALGORITHMS_NEW),

        _Setting('policy.images', 'ImagePolicy', _IMAGE_POLICIES),
        _Setting('contrast', 'ContrastPercent'),
        _Setting('grayscale.all', 'IsGrayScale', _BOOLS),

        _Setting('threshold.text', 'TextBrightnessThreshold'),
        _Setting('threshold.background', 'BackgroundBrightnessThreshold'),
        _Setting('grayscale.images', 'ImageGrayScalePercent'),

        mandatory={'enabled', 'policy.images'},
        prefix='',
        switch_names={'enabled': _BLINK_SETTINGS, None: 'dark-mode-settings'},
    ),

    # Qt 5.15.1 and 5.15.2 get added below, since there are only minor differences.

    Variant.qt_515_0: _Definition(
        # 'policy.images' not mandatory because it's broken
        _Setting('enabled', 'Enabled', _BOOLS),
        _Setting('algorithm', 'InversionAlgorithm', _ALGORITHMS),

        _Setting('policy.images', 'ImagePolicy', _IMAGE_POLICIES),
        _Setting('contrast', 'Contrast'),
        _Setting('grayscale.all', 'Grayscale', _BOOLS),

        _Setting('policy.page', 'PagePolicy', _PAGE_POLICIES),
        _Setting('threshold.text', 'TextBrightnessThreshold'),
        _Setting('threshold.background', 'BackgroundBrightnessThreshold'),
        _Setting('grayscale.images', 'ImageGrayscale'),

        mandatory={'enabled'},
        prefix='darkMode',
    ),

    Variant.qt_514: _Definition(
        _Setting('algorithm', '', _ALGORITHMS),  # new: kInvertLightnessLAB

        _Setting('policy.images', 'ImagePolicy', _IMAGE_POLICIES),
        _Setting('contrast', 'Contrast'),
        _Setting('grayscale.all', 'Grayscale', _BOOLS),

        _Setting('policy.page', 'PagePolicy', _PAGE_POLICIES),
        _Setting('threshold.text', 'TextBrightnessThreshold'),
        _Setting('threshold.background', 'BackgroundBrightnessThreshold'),
        _Setting('grayscale.images', 'ImageGrayscale'),

        mandatory={'algorithm', 'policy.images'},
        prefix='darkMode',
    ),

    Variant.qt_511_to_513: _Definition(
        _Setting('algorithm', 'Mode', _ALGORITHMS_BEFORE_QT_514),

        _Setting('policy.images', 'ImagePolicy', _IMAGE_POLICIES),
        _Setting('contrast', 'Contrast'),
        _Setting('grayscale.all', 'Grayscale', _BOOLS),

        mandatory={'algorithm', 'policy.images'},
        prefix='highContrast',
    ),
}
_DEFINITIONS[Variant.qt_515_1] = (
    _DEFINITIONS[Variant.qt_515_0].copy_with('mandatory', {'enabled', 'policy.images'}))
_DEFINITIONS[Variant.qt_515_2] = (
    _DEFINITIONS[Variant.qt_515_1].copy_with('prefix', 'forceDarkMode'))


_PREFERRED_COLOR_SCHEME_DEFINITIONS = {
    # With older Qt versions, this is passed in qtargs.py as --force-dark-mode
    # instead.

    ## Qt 5.15.2
    # 0: no-preference (not exposed)
    (Variant.qt_515_2, "dark"): "1",
    (Variant.qt_515_2, "light"): "2",
    # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-89753
    # Fall back to "light" instead of "no preference" (which was removed from the
    # standard)
    (Variant.qt_515_2, "auto"): "2",
    (Variant.qt_515_2, usertypes.UNSET): "2",

    ## Qt >= 5.15.3
    (Variant.qt_515_3, "dark"): "0",
    (Variant.qt_515_3, "light"): "1",
}


def _variant(versions: version.WebEngineVersions) -> Variant:
    """Get the dark mode variant based on the underlying Qt version."""
    env_var = os.environ.get('QUTE_DARKMODE_VARIANT')
    if env_var is not None:
        try:
            return Variant[env_var]
        except KeyError:
            log.init.warning(f"Ignoring invalid QUTE_DARKMODE_VARIANT={env_var}")

    if (versions.webengine == utils.VersionNumber(5, 15, 2) and
            versions.chromium_major == 87):
        # WORKAROUND for Gentoo packaging something newer as 5.15.2...
        return Variant.qt_515_3
    elif versions.webengine >= utils.VersionNumber(5, 15, 3):
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


def settings(
        *,
        versions: version.WebEngineVersions,
        special_flags: Sequence[str],
) -> Mapping[str, Sequence[Tuple[str, str]]]:
    """Get necessary blink settings to configure dark mode for QtWebEngine.

    Args:
       Existing '--blink-settings=...' flags, if any.

    Returns:
        A dict which maps Chromium switch names (blink-settings or dark-mode-settings)
        to a sequence of tuples, each tuple being a key/value pair to pass to that
        setting.
    """
    variant = _variant(versions)
    log.init.debug(f"Darkmode variant: {variant.name}")

    result: Mapping[str, List[Tuple[str, str]]] = collections.defaultdict(list)

    blink_settings_flag = f'--{_BLINK_SETTINGS}='
    for flag in special_flags:
        if flag.startswith(blink_settings_flag):
            for pair in flag[len(blink_settings_flag):].split(','):
                key, val = pair.split('=', maxsplit=1)
                result[_BLINK_SETTINGS].append((key, val))

    preferred_color_scheme_key = (
        variant,
        config.instance.get("colors.webpage.preferred_color_scheme", fallback=False),
    )
    if preferred_color_scheme_key in _PREFERRED_COLOR_SCHEME_DEFINITIONS:
        value = _PREFERRED_COLOR_SCHEME_DEFINITIONS[preferred_color_scheme_key]
        result[_BLINK_SETTINGS].append(("preferredColorScheme", value))

    if not config.val.colors.webpage.darkmode.enabled:
        return result

    definition = _DEFINITIONS[variant]

    for switch_name, setting in definition.prefixed_settings():
        # To avoid blowing up the commandline length, we only pass modified
        # settings to Chromium, as our defaults line up with Chromium's.
        # However, we always pass enabled/algorithm to make sure dark mode gets
        # actually turned on.
        value = config.instance.get(
            'colors.webpage.darkmode.' + setting.option,
            fallback=setting.option in definition.mandatory)
        if isinstance(value, usertypes.Unset):
            continue

        if (setting.option == 'policy.images' and value == 'smart' and
                variant == Variant.qt_515_0):
            # WORKAROUND for
            # https://codereview.qt-project.org/c/qt/qtwebengine-chromium/+/304211
            log.init.warning("Ignoring colors.webpage.darkmode.policy.images = smart "
                             "because of Qt 5.15.0 bug")
            continue

        result[switch_name].append(setting.chromium_tuple(value))

    return result
