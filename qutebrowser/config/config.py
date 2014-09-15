# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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
import functools
import configparser
import collections.abc

from PyQt5.QtCore import pyqtSignal, QObject, QCoreApplication

from qutebrowser.utils import log
from qutebrowser.config import configdata, iniparsers, configtypes, textwrapper
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.utils import message
from qutebrowser.utils.usertypes import Completion


def instance():
    """Get the global config instance."""
    return QCoreApplication.instance().config


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


class InterpolationSyntaxError(ValueError):

    """Exception raised when configparser interpolation raised an error."""

    pass


class UnknownSectionError(Exception):

    """Exception raised when there was an unknwon section in the config."""

    pass


class ConfigManager(QObject):

    """Configuration manager for qutebrowser.

    Class attributes:
        KEY_ESCAPE: Chars which need escaping when they occur as first char
                    in a line.
        ESCAPE_CHAR: The char to be used for escaping

    Attributes:
        sections: The configuration data as an OrderedDict.
        _fname: The filename to be opened.
        _configparser: A ReadConfigParser instance to load the config.
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
        self._configparser = iniparsers.ReadConfigParser(configdir, fname)
        self._configfile = os.path.join(configdir, fname)
        self._configdir = configdir
        self._fname = fname
        self._interpolation = configparser.ExtendedInterpolation()
        self._proxies = {}
        for sectname in self.sections.keys():
            self._proxies[sectname] = SectionProxy(self, sectname)
        self._from_cp(self._configparser)

    def __getitem__(self, key):
        """Get a section from the config."""
        return self._proxies[key]

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self._fname)

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
        wrapper = textwrapper.TextWrapper()
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
        wrapper = textwrapper.TextWrapper(initial_indent='#' + ' ' * 5,
                                          subsequent_indent='#' + ' ' * 5)
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
            except KeyError as e:
                log.misc.debug("No description for {}.{}! ({}: {})".format(
                    sectname, optname, e.__class__.__name__, e))
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
            value = option.value(startlayer='conf')
            for c in self.KEY_ESCAPE:
                if optname.startswith(c):
                    optname = optname.replace(c, self.ESCAPE_CHAR + c, 1)
            # configparser can't handle = in keys :(
            optname = optname.replace('=', '<eq>')
            keyval = '{} = {}'.format(optname, value)
            lines.append(keyval)
        return lines

    def _from_cp(self, cp):
        """Read the config from a configparser instance.

        Args:
            cp: The configparser instance to read the values from.
        """
        for sectname in cp:
            if sectname is not 'DEFAULT' and sectname not in self.sections:
                raise UnknownSectionError("Unknown section '{}'!".format(
                    sectname))
        for sectname in self.sections:
            if sectname not in cp:
                continue
            for k, v in cp[sectname].items():
                if k.startswith(self.ESCAPE_CHAR):
                    k = k[1:]
                # configparser can't handle = in keys :(
                k = k.replace('<eq>', '=')
                try:
                    self.set('conf', sectname, k, v)
                except configtypes.ValidationError as e:
                    e.section = sectname
                    e.option = k
                    raise

    def items(self, sectname, raw=True):
        """Get a list of (optname, value) tuples for a section.

        Implemented for configparser interpolation compatbility.

        Args:
            sectname: The name of the section to get.
            raw: Whether to get raw values. Note this parameter only exists
                 for ConfigParser compatibility and raw=False is not supported.
        """
        items = []
        if not raw:
            raise ValueError("items() with raw=True is not implemented!")
        for optname, option in self.sections[sectname].items():
            items.append((optname, option.value()))
        return items

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
            self.get.cache_clear()
        return existed

    @functools.lru_cache()
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
        try:
            sect = self.sections[sectname]
        except KeyError:
            raise NoSectionError(sectname)
        try:
            val = sect[optname]
        except KeyError:
            raise NoOptionError(optname, sectname)
        if raw:
            return val.value()
        mapping = {key: val.value() for key, val in sect.values.items()}
        newval = self._interpolation.before_get(self, sectname, optname,
                                                val.value(), mapping)
        if transformed:
            newval = val.typ.transform(newval)
        return newval

    @cmdutils.register(name='set', instance='config',
                       completion=[Completion.section, Completion.option,
                                   Completion.value])
    def set_command(self, sectname: {'name': 'section'},
                    optname: {'name': 'option'}, value=None, temp=False):
        """Set an option.

        If the option name ends with '?', the value of the option is shown
        instead.

        //

        Wrapper for self.set() to output exceptions in the status bar.

        Args:
            sectname: The section where the option is in.
            optname: The name of the option.
            value: The value to set.
            temp: Set value temporarily.
        """
        try:
            if optname.endswith('?'):
                val = self.get(sectname, optname[:-1], transformed=False)
                message.info("{} {} = {}".format(sectname, optname[:-1], val),
                             immediately=True)
            else:
                if value is None:
                    raise cmdexc.CommandError("set: The following arguments "
                                              "are required: value")
                layer = 'temp' if temp else 'conf'
                self.set(layer, sectname, optname, value)
        except (NoOptionError, NoSectionError, configtypes.ValidationError,
                ValueError) as e:
            raise cmdexc.CommandError("set: {} - {}".format(
                e.__class__.__name__, e))

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
        try:
            value = self._interpolation.before_set(self, sectname, optname,
                                                   value)
        except ValueError as e:
            raise InterpolationSyntaxError(e)
        try:
            sect = self.sections[sectname]
        except KeyError:
            raise NoSectionError(sectname)
        mapping = {key: val.value() for key, val in sect.values.items()}
        interpolated = self._interpolation.before_get(self, sectname, optname,
                                                      value, mapping)
        try:
            sect.setv(layer, optname, value, interpolated)
        except KeyError:
            raise NoOptionError(optname, sectname)
        else:
            self.get.cache_clear()
            if sectname in ('colors', 'fonts'):
                self.style_changed.emit(sectname, optname)
            self.changed.emit(sectname, optname)

    @cmdutils.register(instance='config')
    def save(self):
        """Save the config file."""
        if not os.path.exists(self._configdir):
            os.makedirs(self._configdir, 0o755)
        log.destroy.debug("Saving config to {}".format(self._configfile))
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
        if not lines:
            lines = ['<Default configuration>']
        return '\n'.join(lines)

    def optionxform(self, val):
        """Implemented to be compatible with ConfigParser interpolation."""
        return val


class SectionProxy(collections.abc.MutableMapping):

    """A proxy for a single section from a config.

    Attributes:
        _conf: The Config object.
        _name: The section name.
    """

    def __init__(self, conf, name):
        """Create a view on a section.

        Args:
            conf: The Config object.
            name: The section name.
        """
        self.conf = conf
        self.name = name

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.name)

    def __getitem__(self, key):
        if not self.conf.has_option(self.name, key):
            raise KeyError(key)
        return self.conf.get(self.name, key)

    def __setitem__(self, key, value):
        return self.conf.set('conf', self.name, key, value)

    def __delitem__(self, key):
        if not (self.conf.has_option(self.name, key) and
                self.conf.remove_option(self.name, key)):
            raise KeyError(key)

    def __contains__(self, key):
        return self.conf.has_option(self.name, key)

    def __len__(self):
        return len(self._options())

    def __iter__(self):
        return self._options().__iter__()

    def _options(self):
        """Get the option keys from this section."""
        return self.conf.sections[self.name].keys()

    def get(self, optname, *, raw=False):  # pylint: disable=arguments-differ
        """Get a value from this section.

        We deliberately don't support the default argument here, but have a raw
        argument instead.

        Args:
            optname: The option name to get.
            raw: Whether to get a raw value or not.
        """
        return self.conf.get(self.name, optname, raw=raw)
