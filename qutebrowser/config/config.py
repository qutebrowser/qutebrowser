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

"""Configuration storage and config-related utilities.

This borrows a lot of ideas from configparser, but also has some things that
are fundamentally different. This is why nothing inherts from configparser, but
we borrow some methods and classes from there where it makes sense.
"""

import os
import os.path
import logging
import textwrap
import configparser
from configparser import ExtendedInterpolation
from collections.abc import MutableMapping

from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication

import qutebrowser.config.configdata as configdata
import qutebrowser.commands.utils as cmdutils
import qutebrowser.utils.message as message
from qutebrowser.config.iniparsers import ReadConfigParser
from qutebrowser.config._conftypes import ValidationError


def instance():
    """Get the global config instance."""
    return QApplication.instance().obj['config']


def get(*args, **kwargs):
    """Convenience method to call get(...) of the config instance."""
    return instance().get(*args, **kwargs)


def section(sect):
    """Get a config section from the global config."""
    return instance()[sect]


class NoSectionError(configparser.NoSectionError):

    """Exception raised when a section was not found."""

    pass


class NoOptionError(configparser.NoOptionError):

    """Exception raised when an option was not found."""

    pass


class ConfigManager(QObject):

    """Configuration manager for qutebrowser.

    Class attributes:
        KEY_ESCAPE: Chars which need escaping when they occur as first char
                    in a line.
        ESCAPE_CHAR: The char to be used for escaping

    Attributes:
        sections: The configuration data as an OrderedDict.
        _configparser: A ReadConfigParser instance to load the config.
        _wrapper_args: A dict with the default kwargs for the config wrappers.
        _configdir: The dictionary to read the config from and save it in.
        _configfile: The config file path.
        _interpolation: An configparser.Interpolation object
        _proxies: configparser.SectionProxy objects for sections.

    Signals:
        changed: Gets emitted when the config has changed.
                 Args: the changed section, option and new value.
        style_changed: When style caches need to be invalidated.
                 Args: the changed section and option.
    """

    KEY_ESCAPE = r'\#['
    ESCAPE_CHAR = '\\'

    changed = pyqtSignal(str, str)
    style_changed = pyqtSignal(str, str)

    def __init__(self, configdir, fname, parent=None):
        super().__init__(parent)
        self.sections = configdata.DATA
        self._configparser = ReadConfigParser(configdir, fname)
        self._configfile = os.path.join(configdir, fname)
        self._wrapper_args = {
            'width': 72,
            'replace_whitespace': False,
            'break_long_words': False,
            'break_on_hyphens': False,
        }
        self._configdir = configdir
        self._interpolation = ExtendedInterpolation()
        self._proxies = {}
        for sectname in self.sections.keys():
            self._proxies[sectname] = SectionProxy(self, sectname)
        self._from_cp(self._configparser)

    def __getitem__(self, key):
        """Get a section from the config."""
        return self._proxies[key]

    def __str__(self):
        """Get the whole config as a string."""
        lines = configdata.FIRST_COMMENT.strip('\n').splitlines()
        for sectname, sect in self.sections.items():
            lines.append('\n[{}]'.format(sectname))
            lines += self._str_section_desc(sectname)
            lines += self._str_option_desc(sectname, sect)
            lines += self._str_items(sect)
        return '\n'.join(lines) + '\n'

    def _str_section_desc(self, sectname):
        """Get the section description string for sectname."""
        wrapper = textwrap.TextWrapper(initial_indent='# ',
                                       subsequent_indent='# ',
                                       **self._wrapper_args)
        lines = []
        seclines = configdata.SECTION_DESC[sectname].splitlines()
        for secline in seclines:
            if 'http://' in secline or 'https://' in secline:
                lines.append('# ' + secline)
            else:
                lines += wrapper.wrap(secline)
        return lines

    def _str_option_desc(self, sectname, sect):
        """Get the option description strings for sect/sectname."""
        wrapper = textwrap.TextWrapper(initial_indent='#' + ' ' * 5,
                                       subsequent_indent='#' + ' ' * 5,
                                       **self._wrapper_args)
        lines = []
        if not getattr(sect, 'descriptions', None):
            return lines
        for optname, option in sect.items():
            lines.append('#')
            if option.typ.typestr is None:
                typestr = ''
            else:
                typestr = ' ({})'.format(option.typ.typestr)
            lines.append("# {}{}:".format(optname, typestr))
            try:
                desc = self.sections[sectname].descriptions[optname]
            except KeyError:
                continue
            for descline in desc.splitlines():
                lines += wrapper.wrap(descline)
            valid_values = option.typ.valid_values
            if valid_values is not None:
                if valid_values.descriptions:
                    for val in valid_values:
                        desc = valid_values.descriptions[val]
                        lines += wrapper.wrap("    {}: {}".format(val, desc))
                else:
                    lines += wrapper.wrap("Valid values: {}".format(', '.join(
                        valid_values)))
            lines += wrapper.wrap("Default: {}".format(
                option.values['default']))
        return lines

    def _str_items(self, sect):
        """Get the option items as string for sect."""
        lines = []
        for optname, option in sect.items():
            value = option.get_first_value(startlayer='conf')
            for c in self.KEY_ESCAPE:
                if optname.startswith(c):
                    optname = optname.replace(c, self.ESCAPE_CHAR + c, 1)
            keyval = '{} = {}'.format(optname, value)
            lines.append(keyval)
        return lines

    def _from_cp(self, cp):
        """Read the config from a configparser instance.

        Args:
            cp: The configparser instance to read the values from.
        """
        for sectname in self.sections.keys():
            if sectname not in cp:
                continue
            for k, v in cp[sectname].items():
                if k.startswith(self.ESCAPE_CHAR):
                    k = k[1:]
                try:
                    self.set('conf', sectname, k, v)
                except ValidationError as e:
                    e.section = sectname
                    e.option = k
                    raise

    def has_option(self, sectname, optname):
        """Check if option exists in section.

        Args:
            sectname: The section name.
            optname: The option name

        Return:
            True if the option and section exist, False otherwise.
        """
        if sectname not in self.sections:
            return False
        return optname in self.sections[sectname]

    def remove_option(self, sectname, optname):
        """Remove an option.

        Args:
            sectname: The section where to remove an option.
            optname: The option name to remove.

        Return:
            True if the option existed, False otherwise.
        """
        try:
            sectdict = self.sections[sectname]
        except KeyError:
            raise NoSectionError(sectname)
        optname = self.optionxform(optname)
        existed = optname in sectdict
        if existed:
            del sectdict[optname]
        return existed

    @cmdutils.register(name='get', instance='config',
                       completion=['section', 'option'])
    def get_wrapper(self, sectname, optname):
        """Get the value from a section/option.

        Wrapper for the get-command to output the value in the status bar.
        """
        try:
            val = self.get(sectname, optname, transformed=False)
        except (NoOptionError, NoSectionError) as e:
            message.error("get: {} - {}".format(e.__class__.__name__, e))
        else:
            message.info("{} {} = {}".format(sectname, optname, val))

    def get(self, sectname, optname, raw=False, transformed=True):
        """Get the value from a section/option.

        Args:
            sectname: The section to get the option from.
            optname: The option name
            raw: Whether to get the uninterpolated, untransformed value.
            transformed: Whether the value should be transformed.

        Return:
            The value of the option.
        """
        logging.debug("getting {} -> {}".format(sectname, optname))
        try:
            sect = self.sections[sectname]
        except KeyError:
            raise NoSectionError(sectname)
        try:
            val = sect[optname]
        except KeyError:
            raise NoOptionError(optname, sectname)
        if raw:
            return val.value
        mapping = {key: val.value for key, val in sect.values.items()}
        newval = self._interpolation.before_get(self, sectname, optname,
                                                val.value, mapping)
        logging.debug("interpolated val: {}".format(newval))
        if transformed:
            newval = val.typ.transform(newval)
        return newval

    @cmdutils.register(name='set', instance='config',
                       completion=['section', 'option', 'value'])
    def set_wrapper(self, sectname, optname, value):
        """Set an option.

        Wrapper for self.set() to output exceptions in the status bar.
        """
        try:
            self.set('conf', sectname, optname, value)
        except (NoOptionError, NoSectionError, ValidationError,
                ValueError) as e:
            message.error("set: {} - {}".format(e.__class__.__name__, e))

    @cmdutils.register(name='set_temp', instance='config',
                       completion=['section', 'option', 'value'])
    def set_temp_wrapper(self, sectname, optname, value):
        """Set a temporary option.

        Wrapper for self.set() to output exceptions in the status bar.
        """
        try:
            self.set('temp', sectname, optname, value)
        except (NoOptionError, NoSectionError, ValidationError) as e:
            message.error("set: {} - {}".format(e.__class__.__name__, e))

    def set(self, layer, sectname, optname, value):
        """Set an option.

        Args:
            layer: A layer name as string (conf/temp/default).
            sectname: The name of the section to change.
            optname: The name of the option to change.
            value: The new value.

        Raise:
            NoSectionError: If the specified section doesn't exist.
            NoOptionError: If the specified option doesn't exist.

        Emit:
            changed: If the config was changed.
            style_changed: When style caches need to be invalidated.
        """
        value = self._interpolation.before_set(self, sectname, optname, value)
        try:
            sect = self.sections[sectname]
        except KeyError:
            raise NoSectionError(sectname)
        mapping = {key: val.value for key, val in sect.values.items()}
        interpolated = self._interpolation.before_get(self, sectname, optname,
                                                      value, mapping)
        try:
            sect.setv(layer, optname, value, interpolated)
        except KeyError:
            raise NoOptionError(optname, sectname)
        else:
            if sectname in ['colors', 'fonts']:
                self.style_changed.emit(sectname, optname)
            self.changed.emit(sectname, optname)

    @cmdutils.register(instance='config')
    def save(self):
        """Save the config file."""
        if not os.path.exists(self._configdir):
            os.makedirs(self._configdir, 0o755)
        logging.debug("Saving config to {}".format(self._configfile))
        with open(self._configfile, 'w', encoding='utf-8') as f:
            f.write(str(self))

    def dump_userconfig(self):
        """Get the part of the config which was changed by the user.

        Return:
            The changed config part as string.
        """
        lines = []
        for sectname, sect in self.sections.items():
            changed = sect.dump_userconfig()
            if changed:
                lines.append('[{}]'.format(sectname))
                lines += ['{} = {}'.format(k, v) for k, v in changed]
        return '\n'.join(lines)

    def optionxform(self, val):
        """Implemented to be compatible with ConfigParser interpolation."""
        return val


class SectionProxy(MutableMapping):

    """A proxy for a single section from a config.

    Attributes:
        _conf: The Config object.
        _name: The section name.
    """

    # pylint: disable=redefined-builtin

    def __init__(self, conf, name):
        """Create a view on a section.

        Args:
            conf: The Config object.
            name: The section name.
        """
        self._conf = conf
        self._name = name

    def __repr__(self):
        return '<Section: {}>'.format(self._name)

    def __getitem__(self, key):
        if not self._conf.has_option(self._name, key):
            raise KeyError(key)
        return self._conf.get(self._name, key)

    def __setitem__(self, key, value):
        return self._conf.set('conf', self._name, key, value)

    def __delitem__(self, key):
        if not (self._conf.has_option(self._name, key) and
                self._conf.remove_option(self._name, key)):
            raise KeyError(key)

    def __contains__(self, key):
        return self._conf.has_option(self._name, key)

    def __len__(self):
        return len(self._options())

    def __iter__(self):
        return self._options().__iter__()

    def _options(self):
        """Get the option keys from this section."""
        return self._conf.sections[self._name].keys()

    def get(self, optname, *, raw=False):
        """Get a value from this section.

        We deliberately don't support the default argument here, but have a raw
        argument instead.

        Args:
            optname: The option name to get.
            raw: Whether to get a raw value or not.
        """
        # pylint: disable=arguments-differ
        return self._conf.get(self._name, optname, raw=raw)

    @property
    def conf(self):
        """The conf object of the proxy is read-only."""
        return self._conf

    @property
    def name(self):
        """The name of the section on a proxy is read-only."""
        return self._name
