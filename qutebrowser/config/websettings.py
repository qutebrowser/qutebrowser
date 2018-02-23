# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtGui import QFont

from qutebrowser.config import config, configutils
from qutebrowser.utils import log, usertypes
from qutebrowser.misc import objects

UNSET = object()


class AbstractSettings:

    """Abstract base class for settings set via QWeb(Engine)Settings."""

    _ATTRIBUTES = None
    _FONT_SIZES = None
    _FONT_FAMILIES = None
    _FONT_TO_QFONT = None

    def __init__(self, settings):
        self._settings = settings

    def set_attribute(self, name, value):
        """Set the given QWebSettings/QWebEngineSettings attribute.

        If the value is configutils.UNSET, the value is reset instead.
        """
        for attribute in self._ATTRIBUTES[name]:
            if value is configutils.UNSET:
                self._settings.resetAttribute(attribute)
            else:
                self._settings.setAttribute(attribute, value)

    def test_attribute(self, name):
        """Get the value for the given attribute."""
        return self._settings.testAttribute(self._ATTRIBUTES[name])

    def set_font_size(self, name, value):
        """Set the given QWebSettings/QWebEngineSettings font size."""
        assert value is not configutils.UNSET
        self._settings.setFontSize(self._FONT_SIZES[name], value)

    def set_font_family(self, name, value):
        """Set the given QWebSettings/QWebEngineSettings font family.

        With None (the default), QFont is used to get the default font for the
        family.
        """
        assert value is not configutils.UNSET
        if value is None:
            font = QFont()
            font.setStyleHint(self._FONT_TO_QFONT[self._FONT_FAMILIES[name]])
            value = font.defaultFamily()

        self._settings.setFontFamily(self._FONT_FAMILIES[name], value)

    def set_default_text_encoding(self, encoding):
        """Set the default text encoding to use."""
        assert encoding is not configutils.UNSET
        self._settings.setDefaultTextEncoding(encoding)

    def _update_setting(self, setting, value):
        """Update the given setting/value.

        Unknown settings are ignored.
        """
        if setting in self._ATTRIBUTES:
            self.set_attribute(setting, value)
        elif setting in self._FONT_SIZES:
            self.set_font_size(setting, value)
        elif setting in self._FONT_FAMILIES:
            self.set_font_family(setting, value)
        elif setting == 'content.default_encoding':
            self.set_default_text_encoding(value)

    def update_setting(self, setting):
        """Update the given setting."""
        value = config.instance.get(setting)
        self._update_setting(setting, value)

    def update_for_url(self, url):
        """Update settings customized for the given tab."""
        for values in config.instance:
            if not values.opt.supports_pattern:
                continue

            value = values.get_for_url(url, fallback=False)
            log.config.debug("Updating for {}: {} = {}".format(
                url.toDisplayString(), values.opt.name, value))

            self._update_setting(values.opt.name, value)

    def init_settings(self):
        """Set all supported settings correctly."""
        for setting in (list(self._ATTRIBUTES) + list(self._FONT_SIZES) +
                        list(self._FONT_FAMILIES)):
            self.update_setting(setting)


def init(args):
    """Initialize all QWeb(Engine)Settings."""
    if objects.backend == usertypes.Backend.QtWebEngine:
        from qutebrowser.browser.webengine import webenginesettings
        webenginesettings.init(args)
    else:
        from qutebrowser.browser.webkit import webkitsettings
        webkitsettings.init(args)


def shutdown():
    """Shut down QWeb(Engine)Settings."""
    if objects.backend == usertypes.Backend.QtWebEngine:
        from qutebrowser.browser.webengine import webenginesettings
        webenginesettings.shutdown()
    else:
        from qutebrowser.browser.webkit import webkitsettings
        webkitsettings.shutdown()
