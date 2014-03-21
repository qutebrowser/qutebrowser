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
import os.path
import logging
import textwrap
from configparser import ConfigParser, ExtendedInterpolation

#from qutebrowser.utils.misc import read_file
import qutebrowser.config.configdata as configdata
import qutebrowser.commands.utils as cmdutils

config = None
state = None

# Special value for an unset fallback, so None can be passed as fallback.
_UNSET = object()


def init(configdir):
    """Initialize the global objects based on the config in configdir.

    Args:
        configdir: The directory where the configs are stored in.

    """
    global config, state
    logging.debug("Config init, configdir {}".format(configdir))
    #config = Config(configdir, 'qutebrowser.conf',
    #                read_file('qutebrowser.conf'))
    config = Config(configdir, 'qutebrowser.conf')
    state = ReadWriteConfigParser(configdir, 'state')


class Config:

    """Configuration manager for qutebrowser.

    Attributes:
        config: The configuration data as an OrderedDict.
        _configparser: A ReadConfigParser instance to load the config.
        _wrapper_args: A dict with the default kwargs for the config wrappers.
        _configdir: The dictionary to read the config from and save it in.
        _configfile: The config file path.

    """

    def __init__(self, configdir, fname):
        self.config = configdata.configdata()
        self._configparser = ReadConfigParser(configdir, fname)
        self._configfile = os.path.join(configdir, fname)
        self._wrapper_args = {
            'width': 72,
            'replace_whitespace': False,
            'break_long_words': False,
            'break_on_hyphens': False,
        }
        self._configdir = configdir
        for secname, section in self.config.items():
            try:
                section.from_cp(self._configparser[secname])
            except KeyError:
                pass

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
        return '\n'.join(lines) + '\n'

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
            if valid_values is not None and valid_values.show:
                if valid_values.descriptions:
                    for val in valid_values:
                        desc = valid_values.descriptions[val]
                        lines += wrapper.wrap('    {}: {}'.format(val, desc))
                else:
                    lines += wrapper.wrap('Valid values: {}'.format(', '.join(
                        valid_values)))
            lines += wrapper.wrap('Default: {}'.format(
                option.default_conf if option.default_conf is not None
                else option.default))
        return lines

    def _str_items(self, section):
        """Get the option items as string for section."""
        lines = []
        for optname, option in section.items():
            keyval = '{} = {}'.format(optname, option)
            lines.append(keyval)
        return lines

    @cmdutils.register(instance='config', completion=['setting'])
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
        if not os.path.exists(self._configdir):
            os.makedirs(self._configdir, 0o755)
        logging.debug("Saving config to {}".format(self._configfile))
        with open(self._configfile, 'w') as f:
            f.write(str(self))

    def dump_userconfig(self):
        """Get the part of the config which was changed by the user.

        Return:
            The changed config part as string.

        """
        # FIXME to be implemented
        pass


class ReadConfigParser(ConfigParser):

    """Our own ConfigParser subclass to read the main config.

    Attributes:
        _configdir: The directory to read the config from.
        _configfile: The config file path.

    """

    def __init__(self, configdir, fname):
        """Config constructor.

        Args:
            configdir: Directory to read the config from.
            fname: Filename of the config file.

        """
        super().__init__(interpolation=ExtendedInterpolation())
        self.optionxform = lambda opt: opt  # be case-insensitive
        self._configdir = configdir
        self._configfile = os.path.join(self._configdir, fname)
        if not os.path.isfile(self._configfile):
            return
        logging.debug("Reading config from {}".format(self._configfile))
        self.read(self._configfile)


class ReadWriteConfigParser(ReadConfigParser):

    """ConfigParser subclass used for auxillary config files."""

    def save(self):
        """Save the config file."""
        if not os.path.exists(self._configdir):
            os.makedirs(self._configdir, 0o755)
        logging.debug("Saving config to {}".format(self._configfile))
        with open(self._configfile, 'w') as f:
            self.write(f)
