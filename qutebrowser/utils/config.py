# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Configuration storage and config-related utilities."""

import os
import io
import os.path
import logging
from configparser import (ConfigParser, ExtendedInterpolation, NoSectionError,
                          NoOptionError)

from qutebrowser.utils.misc import read_file

config = None
state = None
colordict = {}
fontdict = {}

# Special value for an unset fallback, so None can be passed as fallback.
_UNSET = object()


def init(confdir):
    """Initialize the global objects based on the config in configdir.

    Args:
        confdir: The directory where the configs are stored in.

    """
    global config, state, colordict, fontdict
    logging.debug("Config init, confdir {}".format(confdir))
    config = Config(confdir, 'qutebrowser.conf', read_file('qutebrowser.conf'))
    state = Config(confdir, 'state', always_save=True)
    try:
        colordict = ColorDict(config['colors'])
    except KeyError:
        colordict = ColorDict()
    fontdict = FontDict(config['fonts'])


def get_stylesheet(template):
    """Format a stylesheet based on a template.

    Args:
        template: The stylesheet template as string.

    Return:
        The formatted template as string.

    """
    return template.strip().format(color=colordict, font=fontdict)


class ColorDict(dict):

    """A dict aimed at Qt stylesheet colors."""

    # FIXME we should validate colors in __setitem__ based on:
    # http://qt-project.org/doc/qt-4.8/stylesheet-reference.html#brush
    # http://www.w3.org/TR/CSS21/syndata.html#color-units

    def __getitem__(self, key):
        """Override dict __getitem__.

        Args:
            key: The key to get from the dict.

        Return:
            If a value wasn't found, return an empty string.
            (Color not defined, so no output in the stylesheet)

            If the key has a .fg. element in it, return  color: X;.
            If the key has a .bg. element in it, return  background-color: X;.

            In all other cases, return the plain value.

        """
        try:
            val = super().__getitem__(key)
        except KeyError:
            return ''
        if 'fg' in key.split('.'):
            return 'color: {};'.format(val)
        elif 'bg' in key.split('.'):
            return 'background-color: {};'.format(val)
        else:
            return val

    def getraw(self, key):
        """Get a value without the transformations done in __getitem__.

        Args:
            key: The key to get from the dict.

        Return:
            A value, or None if the value wasn't found.

        """
        try:
            return super().__getitem__(key)
        except KeyError:
            return None


class FontDict(dict):

    """A dict aimed at Qt stylesheet fonts."""

    def __getitem__(self, key):
        """Override dict __getitem__.

        Args:
            key: The key to get from the dict.

        Return:
            If a value wasn't found, return an empty string.
            (Color not defined, so no output in the stylesheet)

            In all other cases, return font: <value>.

        """
        try:
            val = super().__getitem__(key)
        except KeyError:
            return ''
        else:
            return 'font: {};'.format(val)

    def getraw(self, key):
        """Get a value without the transformations done in __getitem__.

        Args:
            key: The key to get from the dict.

        Return:
            A value, or None if the value wasn't found.

        """
        try:
            return super().__getitem__(key)
        except KeyError:
            return None


class Config(ConfigParser):

    """Our own ConfigParser subclass.

    Attributes:
        _configdir: The dictionary to save the config in.
        _default_cp: The ConfigParser instance supplying the default values.
        _config_loaded: Whether the config was loaded successfully.

    """

    def __init__(self, configdir, fname, default_config=None,
                 always_save=False):
        """Config constructor.

        Args:
            configdir: Directory to store the config in.
            fname: Filename of the config file.
            default_config: Default config as string.
            always_save: Whether to always save the config, even when it wasn't
                         loaded.

        """
        super().__init__(interpolation=ExtendedInterpolation())
        self._config_loaded = False
        self.always_save = always_save
        self._configdir = configdir
        self._default_cp = ConfigParser(interpolation=ExtendedInterpolation())
        self._default_cp.optionxform = lambda opt: opt  # be case-insensitive
        if default_config is not None:
            self._default_cp.read_string(default_config)
        if not self._configdir:
            return
        self.optionxform = lambda opt: opt  # be case-insensitive
        self._configdir = configdir
        self.configfile = os.path.join(self._configdir, fname)
        if not os.path.isfile(self.configfile):
            return
        logging.debug("Reading config from {}".format(self.configfile))
        self.read(self.configfile)
        self._config_loaded = True

    def __getitem__(self, key):
        """Get an item from the configparser or default dict.

        Extend ConfigParser's __getitem__.

        Args:
            key: The key to get from the dict.

        Return:
            The value of the main or fallback ConfigParser.

        """
        try:
            return super().__getitem__(key)
        except KeyError:
            return self._default_cp[key]

    def get(self, *args, raw=False, vars=None, fallback=_UNSET):
        """Get an item from the configparser or default dict.

        Extend ConfigParser's get().

        This is a bit of a hack, but it (hopefully) works like this:
            - Get value from original configparser.
            - If that's not available, try the default_cp configparser
            - If that's not available, try the fallback given as kwarg
            - If that's not available, we're doomed.

        Args:
            *args: Passed to the other configparsers.
            raw: Passed to the other configparsers (do not interpolate).
            var: Passed to the other configparsers.
            fallback: Fallback value if value wasn't found in any configparser.

        Raise:
            configparser.NoSectionError/configparser.NoOptionError if the
            default configparser raised them and there is no fallback.

        """
        # pylint: disable=redefined-builtin
        # The arguments returned by the ConfigParsers actually are strings
        # already, but we add an explicit str() here to trick pylint into
        # thinking a string is returned (rather than an object) to avoid
        # maybe-no-member errors.
        try:
            return str(super().get(*args, raw=raw, vars=vars))
        except (NoSectionError, NoOptionError):
            pass
        try:
            return str(self._default_cp.get(*args, raw=raw, vars=vars))
        except (NoSectionError, NoOptionError):
            if fallback is _UNSET:
                raise
            else:
                return fallback

    def save(self):
        """Save the config file."""
        if self._configdir is None or (not self._config_loaded and
                                       not self.always_save):
            logging.warning("Not saving config (dir {}, config {})".format(
                self._configdir, 'loaded' if self._config_loaded
                else 'not loaded'))
            return
        if not os.path.exists(self._configdir):
            os.makedirs(self._configdir, 0o755)
        logging.debug("Saving config to {}".format(self.configfile))
        with open(self.configfile, 'w') as f:
            self.write(f)
            f.flush()
            os.fsync(f.fileno())

    def dump_userconfig(self):
        """Get the part of the config which was changed by the user.

        Return:
            The changed config part as string.

        """
        with io.StringIO() as f:
            self.write(f)
            return f.getvalue()
