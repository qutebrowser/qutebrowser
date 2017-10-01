# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# We get various "abstract but not overridden" warnings
# pylint: disable=abstract-method

"""Bridge from QWeb(Engine)Settings to our own settings."""

from PyQt5.QtGui import QFont

from qutebrowser.config import config
from qutebrowser.utils import log, utils, debug, usertypes
from qutebrowser.misc import objects

UNSET = object()


class Base:

    """Base class for QWeb(Engine)Settings wrappers."""

    def __init__(self, default=UNSET):
        self._default = default

    def _get_global_settings(self):
        """Get a list of global QWeb(Engine)Settings to use."""
        raise NotImplementedError

    def _get_settings(self, settings):
        """Get a list of QWeb(Engine)Settings objects to use.

        Args:
            settings: The QWeb(Engine)Settings instance to use, or None to use
                      the global instance.

        Return:
            A list of QWeb(Engine)Settings objects. The first one should be
            used for reading.
        """
        if settings is None:
            return self._get_global_settings()
        else:
            return [settings]

    def set(self, value, settings=None):
        """Set the value of this setting.

        Args:
            value: The value to set, or None to restore the default.
            settings: The QWeb(Engine)Settings instance to use, or None to use
                      the global instance.
        """
        if value is None:
            self.set_default(settings=settings)
        else:
            self._set(value, settings=settings)

    def set_default(self, settings=None):
        """Set the default value for this setting.

        Not implemented for most settings.
        """
        if self._default is UNSET:
            raise ValueError("No default set for {!r}".format(self))
        else:
            self._set(self._default, settings=settings)

    def _set(self, value, settings):
        """Inner function to set the value of this setting.

        Must be overridden by subclasses.

        Args:
            value: The value to set.
            settings: The QWeb(Engine)Settings instance to use, or None to use
                      the global instance.
        """
        raise NotImplementedError


class Attribute(Base):

    """A setting set via QWeb(Engine)Settings::setAttribute.

    Attributes:
        self._attributes: A list of QWeb(Engine)Settings::WebAttribute members.
    """

    ENUM_BASE = None

    def __init__(self, *attributes, default=UNSET):
        super().__init__(default=default)
        self._attributes = list(attributes)

    def __repr__(self):
        attributes = [debug.qenum_key(self.ENUM_BASE, attr)
                      for attr in self._attributes]
        return utils.get_repr(self, attributes=attributes, constructor=True)

    def _set(self, value, settings=None):
        for obj in self._get_settings(settings):
            for attribute in self._attributes:
                obj.setAttribute(attribute, value)


class Setter(Base):

    """A setting set via a QWeb(Engine)Settings setter method.

    This will pass the QWeb(Engine)Settings instance ("self") as first argument
    to the methods, so self._setter is the *unbound* method.

    Attributes:
        _setter: The unbound QWeb(Engine)Settings method to set this value.
        _args: An iterable of the arguments to pass to the setter (before the
               value).
        _unpack: Whether to unpack args (True) or pass them directly (False).
    """

    def __init__(self, setter, args=(), unpack=False, default=UNSET):
        super().__init__(default=default)
        self._setter = setter
        self._args = args
        self._unpack = unpack

    def __repr__(self):
        return utils.get_repr(self, setter=self._setter, args=self._args,
                              unpack=self._unpack, constructor=True)

    def _set(self, value, settings=None):
        for obj in self._get_settings(settings):
            args = [obj]
            args.extend(self._args)
            if self._unpack:
                args.extend(value)
            else:
                args.append(value)
            self._setter(*args)


class StaticSetter(Setter):

    """A setting set via a static QWeb(Engine)Settings method.

    self._setter is the *bound* method.
    """

    def _set(self, value, settings=None):
        if settings is not None:
            raise ValueError("'settings' may not be set with StaticSetters!")
        args = list(self._args)
        if self._unpack:
            args.extend(value)
        else:
            args.append(value)
        self._setter(*args)


class FontFamilySetter(Setter):

    """A setter for a font family.

    Gets the default value from QFont.
    """

    def __init__(self, setter, font, qfont):
        super().__init__(setter=setter, args=[font])
        self._qfont = qfont

    def set_default(self, settings=None):
        font = QFont()
        font.setStyleHint(self._qfont)
        value = font.defaultFamily()
        self._set(value, settings=settings)


def init_mappings(mappings):
    """Initialize all settings based on a settings mapping."""
    for option, mapping in mappings.items():
        value = config.instance.get(option)
        log.config.vdebug("Setting {} to {!r}".format(option, value))
        mapping.set(value)


def update_mappings(mappings, option):
    """Update global settings when QWeb(Engine)Settings changed."""
    try:
        mapping = mappings[option]
    except KeyError:
        return
    value = config.instance.get(option)
    mapping.set(value)


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
