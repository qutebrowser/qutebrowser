# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from qutebrowser.config import config
from qutebrowser.utils import log, utils, debug, objreg

UNSET = object()


class Base:

    """Base class for QWeb(Engine)Settings wrappers.

    Attributes:
        _default: The default value of this setting.
    """

    # Needs to be overridden by subclasses in
    # webkitsettings.py/webenginesettings.py
    GLOBAL_SETTINGS = None

    def __init__(self):
        self._default = UNSET

    def _get_settings(self, settings):
        """Get the QWeb(Engine)Settings object to use.

        Args:
            settings: The QWeb(Engine)Settings instance to use, or None to use
                      the global instance.
        """
        if settings is None:
            return self.GLOBAL_SETTINGS()  # pylint: disable=not-callable
        else:
            return settings

    def save_default(self, settings=None):
        """Save the default value based on the currently set one.

        This does nothing if no getter is configured for this setting.

        Args:
            settings: The QWeb(Engine)Settings instance to use, or None to use
                      the global instance.

        Return:
            The saved default value.
        """
        try:
            self._default = self.get(settings)
            return self._default
        except AttributeError:
            return None

    def restore_default(self, settings=None):
        """Restore the default value from the saved one.

        This does nothing if the default has never been set.

        Args:
            settings: The QWeb(Engine)Settings instance to use, or None to use
                      the global instance.
        """
        if self._default is not UNSET:
            log.config.vdebug("Restoring default {!r}.".format(self._default))
            self._set(self._default, settings=settings)

    def get(self, settings=None):
        """Get the value of this setting.

        Must be overridden by subclasses.

        Args:
            settings: The QWeb(Engine)Settings instance to use, or None to use
                      the global instance.
        """
        raise NotImplementedError

    def set(self, value, settings=None):
        """Set the value of this setting.

        Args:
            value: The value to set.
            settings: The QWeb(Engine)Settings instance to use, or None to use
                      the global instance.
        """
        if value is None:
            self.restore_default(settings)
        else:
            self._set(value, settings=settings)

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
        self._attribute: A QWeb(Engine)Settings::WebAttribute instance.
    """

    ENUM_BASE = None

    def __init__(self, attribute):
        super().__init__()
        self._attribute = attribute

    def __repr__(self):
        return utils.get_repr(
            self, attribute=debug.qenum_key(self.ENUM_BASE, self._attribute),
            constructor=True)

    def get(self, settings=None):
        return self._get_settings(settings).attribute(self._attribute)

    def _set(self, value, settings=None):
        self._get_settings(settings).setAttribute(self._attribute, value)


class Setter(Base):

    """A setting set via QWeb(Engine)Settings getter/setter methods.

    This will pass the QWeb(Engine)Settings instance ("self") as first argument
    to the methods, so self._getter/self._setter are the *unbound* methods.

    Attributes:
        _getter: The unbound QWeb(Engine)Settings method to get this value, or
                 None.
        _setter: The unbound QWeb(Engine)Settings method to set this value.
        _args: An iterable of the arguments to pass to the setter/getter
               (before the value, for the setter).
        _unpack: Whether to unpack args (True) or pass them directly (False).
    """

    def __init__(self, getter, setter, args=(), unpack=False):
        super().__init__()
        self._getter = getter
        self._setter = setter
        self._args = args
        self._unpack = unpack

    def __repr__(self):
        return utils.get_repr(self, getter=self._getter, setter=self._setter,
                              args=self._args, unpack=self._unpack,
                              constructor=True)

    def get(self, settings=None):
        if self._getter is None:
            raise AttributeError("No getter set!")
        return self._getter(self._get_settings(settings), *self._args)

    def _set(self, value, settings=None):
        args = [self._get_settings(settings)]
        args.extend(self._args)
        if self._unpack:
            args.extend(value)
        else:
            args.append(value)
        self._setter(*args)


class NullStringSetter(Setter):

    """A setter for settings requiring a null QString as default.

    This overrides save_default so None is saved for an empty string. This is
    needed for the CSS media type, because it returns an empty Python string
    when getting the value, but setting it to the default requires passing None
    (a null QString) instead of an empty string.
    """

    def save_default(self, settings=None):
        try:
            val = self.get(settings)
        except AttributeError:
            return None
        if val == '':
            self._set(None, settings=settings)
        else:
            self._set(val, settings=settings)
        return val


class StaticSetter(Setter):

    """A setting set via static QWeb(Engine)Settings getter/setter methods.

    self._getter/self._setter are the *bound* methods.
    """

    def get(self, settings=None):
        if settings is not None:
            raise ValueError("'settings' may not be set with GlobalSetters!")
        if self._getter is None:
            raise AttributeError("No getter set!")
        return self._getter(*self._args)

    def _set(self, value, settings=None):
        if settings is not None:
            raise ValueError("'settings' may not be set with GlobalSetters!")
        args = list(self._args)
        if self._unpack:
            args.extend(value)
        else:
            args.append(value)
        self._setter(*args)


def init_mappings(mappings):
    """Initialize all settings based on a settings mapping."""
    for sectname, section in mappings.items():
        for optname, mapping in section.items():
            default = mapping.save_default()
            log.config.vdebug("Saved default for {} -> {}: {!r}".format(
                sectname, optname, default))
            value = config.get(sectname, optname)
            log.config.vdebug("Setting {} -> {} to {!r}".format(
                sectname, optname, value))
            mapping.set(value)


def update_mappings(mappings, section, option):
    """Update global settings when QWeb(Engine)Settings changed."""
    try:
        mapping = mappings[section][option]
    except KeyError:
        return
    value = config.get(section, option)
    mapping.set(value)


def init(args):
    """Initialize all QWeb(Engine)Settings."""
    if args.backend == 'webengine':
        from qutebrowser.browser.webengine import webenginesettings
        webenginesettings.init(args)
    else:
        from qutebrowser.browser.webkit import webkitsettings
        webkitsettings.init(args)


def shutdown():
    """Shut down QWeb(Engine)Settings."""
    if objreg.get('args').backend == 'webengine':
        from qutebrowser.browser.webengine import webenginesettings
        webenginesettings.shutdown()
    else:
        from qutebrowser.browser.webkit import webkitsettings
        webkitsettings.shutdown()
