# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Bridge from QWeb(Engine)Settings to our own settings."""

import typing
import argparse

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QFont

from qutebrowser.config import config, configutils
from qutebrowser.utils import log, usertypes, urlmatch, qtutils
from qutebrowser.misc import objects

UNSET = object()


class AttributeInfo:

    """Info about a settings attribute."""

    def __init__(self, *attributes: typing.Any,
                 converter: typing.Callable = None) -> None:
        self.attributes = attributes
        if converter is None:
            self.converter = lambda val: val
        else:
            self.converter = converter


class AbstractSettings:

    """Abstract base class for settings set via QWeb(Engine)Settings."""

    _ATTRIBUTES = {}  # type: typing.Dict[str, AttributeInfo]
    _FONT_SIZES = {}  # type: typing.Dict[str, typing.Any]
    _FONT_FAMILIES = {}  # type: typing.Dict[str, typing.Any]
    _FONT_TO_QFONT = {}  # type: typing.Dict[typing.Any, QFont.StyleHint]

    def __init__(self, settings: typing.Any) -> None:
        self._settings = settings

    def set_attribute(self, name: str, value: typing.Any) -> bool:
        """Set the given QWebSettings/QWebEngineSettings attribute.

        If the value is configutils.UNSET, the value is reset instead.

        Return:
            True if there was a change, False otherwise.
        """
        old_value = self.test_attribute(name)

        info = self._ATTRIBUTES[name]
        for attribute in info.attributes:
            if value is configutils.UNSET:
                self._settings.resetAttribute(attribute)
                new_value = self.test_attribute(name)
            else:
                self._settings.setAttribute(attribute, info.converter(value))
                new_value = value

        return old_value != new_value

    def test_attribute(self, name: str) -> bool:
        """Get the value for the given attribute.

        If the setting resolves to a list of attributes, only the first
        attribute is tested.
        """
        info = self._ATTRIBUTES[name]
        return self._settings.testAttribute(info.attributes[0])

    def set_font_size(self, name: str, value: int) -> bool:
        """Set the given QWebSettings/QWebEngineSettings font size.

        Return:
            True if there was a change, False otherwise.
        """
        assert value is not configutils.UNSET  # type: ignore
        family = self._FONT_SIZES[name]
        old_value = self._settings.fontSize(family)
        self._settings.setFontSize(family, value)
        return old_value != value

    def set_font_family(self, name: str, value: typing.Optional[str]) -> bool:
        """Set the given QWebSettings/QWebEngineSettings font family.

        With None (the default), QFont is used to get the default font for the
        family.

        Return:
            True if there was a change, False otherwise.
        """
        assert value is not configutils.UNSET  # type: ignore
        family = self._FONT_FAMILIES[name]
        if value is None:
            font = QFont()
            font.setStyleHint(self._FONT_TO_QFONT[family])
            value = font.defaultFamily()

        old_value = self._settings.fontFamily(family)
        self._settings.setFontFamily(family, value)

        return value != old_value

    def set_default_text_encoding(self, encoding: str) -> bool:
        """Set the default text encoding to use.

        Return:
            True if there was a change, False otherwise.
        """
        assert encoding is not configutils.UNSET  # type: ignore
        old_value = self._settings.defaultTextEncoding()
        self._settings.setDefaultTextEncoding(encoding)
        return old_value != encoding

    def _update_setting(self, setting: str, value: typing.Any) -> bool:
        """Update the given setting/value.

        Unknown settings are ignored.

        Return:
            True if there was a change, False otherwise.
        """
        if setting in self._ATTRIBUTES:
            return self.set_attribute(setting, value)
        elif setting in self._FONT_SIZES:
            return self.set_font_size(setting, value)
        elif setting in self._FONT_FAMILIES:
            return self.set_font_family(setting, value)
        elif setting == 'content.default_encoding':
            return self.set_default_text_encoding(value)
        return False

    def update_setting(self, setting: str) -> None:
        """Update the given setting."""
        value = config.instance.get(setting)
        self._update_setting(setting, value)

    def update_for_url(self, url: QUrl) -> typing.Set[str]:
        """Update settings customized for the given tab.

        Return:
            A set of settings which actually changed.
        """
        qtutils.ensure_valid(url)
        changed_settings = set()
        for values in config.instance:
            if not values.opt.supports_pattern:
                continue

            value = values.get_for_url(url, fallback=False)

            changed = self._update_setting(values.opt.name, value)
            if changed:
                log.config.debug("Changed for {}: {} = {}".format(
                    url.toDisplayString(), values.opt.name, value))
                changed_settings.add(values.opt.name)

        return changed_settings

    def init_settings(self) -> None:
        """Set all supported settings correctly."""
        for setting in (list(self._ATTRIBUTES) + list(self._FONT_SIZES) +
                        list(self._FONT_FAMILIES)):
            self.update_setting(setting)


def init(args: argparse.Namespace) -> None:
    """Initialize all QWeb(Engine)Settings."""
    if objects.backend == usertypes.Backend.QtWebEngine:
        from qutebrowser.browser.webengine import webenginesettings
        webenginesettings.init(args)
    else:
        from qutebrowser.browser.webkit import webkitsettings
        webkitsettings.init(args)

    # Make sure special URLs always get JS support
    for pattern in ['file://*', 'chrome://*/*', 'qute://*/*']:
        config.instance.set_obj('content.javascript.enabled', True,
                                pattern=urlmatch.UrlPattern(pattern))


def shutdown() -> None:
    """Shut down QWeb(Engine)Settings."""
    if objects.backend == usertypes.Backend.QtWebEngine:
        from qutebrowser.browser.webengine import webenginesettings
        webenginesettings.shutdown()
    else:
        from qutebrowser.browser.webkit import webkitsettings
        webkitsettings.shutdown()
