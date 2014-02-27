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
import textwrap
from configparser import (ConfigParser, ExtendedInterpolation, NoSectionError,
                          NoOptionError)

#from qutebrowser.utils.misc import read_file
import qutebrowser.config.configdata as configdata

config = None
state = None

# Special value for an unset fallback, so None can be passed as fallback.
_UNSET = object()


def init(confdir):
    """Initialize the global objects based on the config in configdir.

    Args:
        confdir: The directory where the configs are stored in.

    """
    global config, state
    logging.debug("Config init, confdir {}".format(confdir))
    #config = Config(confdir, 'qutebrowser.conf',
    #                read_file('qutebrowser.conf'))
    config = NewConfig()
    state = Config(confdir, 'state', always_save=True)


class NewConfig:

    """New configuration manager."""

    def __init__(self):
        self.config = configdata.configdata()
        self._wrapper_args = {
            'width': 72,
            'replace_whitespace': False,
            'break_long_words': False,
            'break_on_hyphens': False,
        }

    def __getitem__(self, key):
        """Get a section from the config."""
        return self.config[key]

    def __str__(self):
        """Get the whole config as a string."""
        lines = configdata.FIRST_COMMENT.strip('\n').splitlines()
        for secname, section in self.config.items():
            lines.append('\n[{}]'.format(secname))
            lines += self._str_section_desc(secname)
            lines += self._str_option_desc(secname, section)
            lines += self._str_items(section)
        return '\n'.join(lines)

    def _str_section_desc(self, secname):
        """Get the section description string for secname."""
        wrapper = textwrap.TextWrapper(initial_indent='# ',
                                       subsequent_indent='# ',
                                       **self._wrapper_args)
        lines = []
        seclines = configdata.SECTION_DESC[secname].splitlines()
        for secline in seclines:
            if 'http://' in secline:
                lines.append('# ' + secline)
            else:
                lines += wrapper.wrap(secline)
        return lines

    def _str_option_desc(self, secname, section):
        """Get the option description strings for section/secname."""
        wrapper = textwrap.TextWrapper(initial_indent='#' + ' ' * 5,
                                       subsequent_indent='#' + ' ' * 5,
                                       **self._wrapper_args)
        lines = []
        if not section.descriptions:
            return lines
        for optname, option in section.items():
            lines.append('#')
            if option.typ.typestr is None:
                typestr = ''
            else:
                typestr = ' ({})'.format(option.typ.typestr)
            lines.append('# {}{}:'.format(optname, typestr))
            try:
                desc = self.config[secname].descriptions[optname]
            except KeyError:
                continue
            for descline in desc.splitlines():
                lines += wrapper.wrap(descline)
            valid_values = option.typ.valid_values
            if valid_values is not None and option.typ.show_valid_values:
                if isinstance(valid_values[0], str):
                    lines += wrapper.wrap('Valid values: {}'.format(', '.join(
                        valid_values)))
                else:
                    for (val, desc) in valid_values:
                        lines += wrapper.wrap('    {}: {}'.format(val, desc))
            lines += wrapper.wrap('Default: {}'.format(
                option.default_conf if option.default_conf is not None
                else option.default))
        return lines

    def _str_items(self, section):
        """Get the option items as string for section."""
        keyval_wrapper = textwrap.TextWrapper(initial_indent='',
                                              subsequent_indent=' ' * 4,
                                              drop_whitespace=False,
                                              **self._wrapper_args)
        lines = []
        for optname, option in section.items():
            keyval = '{} = {}'.format(optname, option)
            if 'http://' in keyval:
                lines.append(keyval)
            else:
                lines += keyval_wrapper.wrap(keyval)
        return lines

    def get(self, section, option, fallback=_UNSET):
        """Get the real (transformed) value from a section/option."""
        try:
            val = self.config[section][option]
        except KeyError:
            if fallback is _UNSET:
                raise
            else:
                return fallback
        else:
            return val.value

    def save(self):
        """Save the config file."""
        # FIXME to be implemented
        pass

    def dump_userconfig(self):
        """Get the part of the config which was changed by the user.

        Return:
            The changed config part as string.

        """
        # FIXME to be implemented
        pass


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
