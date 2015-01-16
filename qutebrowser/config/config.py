# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import sys
import os.path
import functools
import configparser
import collections
import collections.abc

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QStandardPaths, QUrl
from PyQt5.QtWidgets import QMessageBox

from qutebrowser.config import configdata, configexc, textwrapper
from qutebrowser.config.parsers import ini, keyconf
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.utils import message, objreg, utils, standarddir, log, qtutils
from qutebrowser.utils.usertypes import Completion


class change_filter:  # pylint: disable=invalid-name

    """Decorator to register a new command handler.

    This could also be a function, but as a class (with a "wrong" name) it's
    much cleaner to implement.

    Attributes:
        _sectname: The section to be filtered.
        _optname: The option to be filtered.
    """

    def __init__(self, sectname, optname=None):
        """Save decorator arguments.

        Gets called on parse-time with the decorator arguments.

        Args:
            See class attributes.
        """
        if sectname not in configdata.DATA:
            raise configexc.NoSectionError(sectname)
        if optname is not None and optname not in configdata.DATA[sectname]:
            raise configexc.NoOptionError(optname, sectname)
        self._sectname = sectname
        self._optname = optname

    def __call__(self, func):
        """Register the command before running the function.

        Gets called when a function should be decorated.

        Adds a filter which returns if we're not interested in the change-event
        and calls the wrapped function if we are.

        We assume the function passed doesn't take any parameters.

        Args:
            func: The function to be decorated.

        Return:
            The decorated function.
        """

        @pyqtSlot(str, str)
        @functools.wraps(func)
        def wrapper(wrapper_self, sectname=None, optname=None):
            # pylint: disable=missing-docstring
            if sectname is None and optname is None:
                # Called directly, not from a config change event.
                return func(wrapper_self)
            elif sectname != self._sectname:
                return
            elif self._optname is not None and optname != self._optname:
                return
            else:
                return func(wrapper_self)

        return wrapper


def get(*args, **kwargs):
    """Convenience method to call get(...) of the config instance."""
    return objreg.get('config').get(*args, **kwargs)


def section(sect):
    """Get a config section from the global config."""
    return objreg.get('config')[sect]


def init(args):
    """Initialize the config.

    Args:
        args: The argparse namespace.
    """
    confdir = standarddir.get(QStandardPaths.ConfigLocation, args)
    try:
        app = objreg.get('app')
        config_obj = ConfigManager(confdir, 'qutebrowser.conf', app)
    except (configexc.Error, configparser.Error, UnicodeDecodeError) as e:
        log.init.exception(e)
        errstr = "Error while reading config:"
        try:
            errstr += "\n\n{} -> {}:".format(
                e.section, e.option)  # pylint: disable=no-member
        except AttributeError:
            pass
        errstr += "\n{}".format(e)
        msgbox = QMessageBox(QMessageBox.Critical,
                             "Error while reading config!", errstr)
        msgbox.exec_()
        # We didn't really initialize much so far, so we just quit hard.
        sys.exit(1)
    else:
        objreg.register('config', config_obj)
    try:
        key_config = keyconf.KeyConfigParser(confdir, 'keys.conf')
    except (keyconf.KeyConfigError, UnicodeDecodeError) as e:
        log.init.exception(e)
        errstr = "Error while reading key config:\n"
        if e.lineno is not None:
            errstr += "In line {}: ".format(e.lineno)
        errstr += str(e)
        msgbox = QMessageBox(QMessageBox.Critical,
                             "Error while reading key config!", errstr)
        msgbox.exec_()
        # We didn't really initialize much so far, so we just quit hard.
        sys.exit(1)
    else:
        objreg.register('key-config', key_config)

    datadir = standarddir.get(QStandardPaths.DataLocation, args)
    state_config = ini.ReadWriteConfigParser(datadir, 'state')
    objreg.register('state-config', state_config)
    # We need to import this here because lineparser needs config.
    from qutebrowser.config.parsers import line
    command_history = line.LineConfigParser(datadir, 'cmd-history',
                                            ('completion', 'history-length'))
    objreg.register('command-history', command_history)


class ConfigManager(QObject):

    """Configuration manager for qutebrowser.

    Class attributes:
        KEY_ESCAPE: Chars which need escaping when they occur as first char
                    in a line.
        ESCAPE_CHAR: The char to be used for escaping
        RENAMED_SECTIONS: A mapping of renamed sections, {'oldname': 'newname'}
        RENAMED_OPTIONS: A mapping of renamed options,
                         {('section', 'oldname'): 'newname'}

    Attributes:
        sections: The configuration data as an OrderedDict.
        _fname: The filename to be opened.
        _configdir: The dictionary to read the config from and save it in.
        _interpolation: An configparser.Interpolation object
        _proxies: configparser.SectionProxy objects for sections.
        _initialized: Whether the ConfigManager is fully initialized yet.

    Signals:
        changed: Emitted when a config option changed.
        style_changed: When style caches need to be invalidated.
                 Args: the changed section and option.
    """

    KEY_ESCAPE = r'\#['
    ESCAPE_CHAR = '\\'
    RENAMED_SECTIONS = {
        'permissions': 'content'
    }
    RENAMED_OPTIONS = {
        ('colors', 'tab.fg.odd'): 'tabs.fg.odd',
        ('colors', 'tab.fg.even'): 'tabs.fg.even',
        ('colors', 'tab.fg.selected'): 'tabs.fg.selected',
        ('colors', 'tab.bg.odd'): 'tabs.bg.odd',
        ('colors', 'tab.bg.even'): 'tabs.bg.even',
        ('colors', 'tab.bg.selected'): 'tabs.bg.selected',
        ('colors', 'tab.bg.bar'): 'tabs.bg.bar',
        ('colors', 'tab.indicator.start'): 'tabs.indicator.start',
        ('colors', 'tab.indicator.stop'): 'tabs.indicator.stop',
        ('colors', 'tab.indicator.error'): 'tabs.indicator.error',
        ('colors', 'tab.indicator.system'): 'tabs.indicator.system',
        ('colors', 'tab.seperator'): 'tabs.seperator',
    }

    changed = pyqtSignal(str, str)
    style_changed = pyqtSignal(str, str)

    def __init__(self, configdir, fname, parent=None):
        super().__init__(parent)
        self._initialized = False
        self.sections = configdata.DATA
        self._interpolation = configparser.ExtendedInterpolation()
        self._proxies = {}
        for sectname in self.sections.keys():
            self._proxies[sectname] = SectionProxy(self, sectname)
        self._fname = fname
        if configdir is None:
            self._configdir = None
            self._initialized = True
        else:
            self._configdir = configdir
            parser = ini.ReadConfigParser(configdir, fname)
            self._from_cp(parser)
            self._initialized = True
            self._validate_all()

    def __getitem__(self, key):
        """Get a section from the config."""
        return self._proxies[key]

    def __repr__(self):
        return utils.get_repr(self, fname=self._fname)

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
            except KeyError:
                log.misc.exception("No description for {}.{}!".format(
                    sectname, optname))
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

    def _get_real_sectname(self, cp, sectname):
        """Get an old or new section name based on a configparser.

        This checks if sectname is in cp, and if not, migrates it if needed and
        tries again.

        Args:
            cp: The configparser to check.
            sectname: The new section name.

        Returns:
            The section name in the configparser as a string, or None if the
            configparser doesn't contain the section.
        """
        reverse_renamed_sections = {v: k for k, v in
                                    self.RENAMED_SECTIONS.items()}
        if sectname in reverse_renamed_sections:
            old_sectname = reverse_renamed_sections[sectname]
        else:
            old_sectname = sectname
        if old_sectname in cp:
            return old_sectname
        elif sectname in cp:
            return sectname
        else:
            return None

    def _from_cp(self, cp):
        """Read the config from a configparser instance.

        Args:
            cp: The configparser instance to read the values from.
        """
        for sectname in cp:
            if sectname in self.RENAMED_SECTIONS:
                sectname = self.RENAMED_SECTIONS[sectname]
            if sectname is not 'DEFAULT' and sectname not in self.sections:
                raise configexc.NoSectionError(sectname)
        for sectname in self.sections:
            real_sectname = self._get_real_sectname(cp, sectname)
            if real_sectname is None:
                continue
            for k, v in cp[real_sectname].items():
                if k.startswith(self.ESCAPE_CHAR):
                    k = k[1:]
                if (sectname, k) in self.RENAMED_OPTIONS:
                    k = self.RENAMED_OPTIONS[sectname, k]
                self.set('conf', sectname, k, v, validate=False)

    def _validate_all(self):
        """Validate all values set in self._from_cp."""
        for sectname, sect in self.sections.items():
            mapping = {key: val.value() for key, val in sect.values.items()}
            for optname, opt in sect.items():
                interpolated = self._interpolation.before_get(
                    self, sectname, optname, opt.value(), mapping)
                try:
                    opt.typ.validate(interpolated)
                except configexc.ValidationError as e:
                    e.section = sectname
                    e.option = optname
                    raise

    def _changed(self, sectname, optname):
        """Notify other objects the config has changed."""
        log.misc.debug("Config option changed: {} -> {}".format(
            sectname, optname))
        if sectname in ('colors', 'fonts'):
            self.style_changed.emit(sectname, optname)
        self.changed.emit(sectname, optname)

    def _after_set(self, changed_sect, changed_opt):
        """Clean up caches and emit signals after an option has been set."""
        self.get.cache_clear()
        self._changed(changed_sect, changed_opt)
        # Options in the same section and ${optname} interpolation.
        for optname, option in self.sections[changed_sect].items():
            if '${' + changed_opt + '}' in option.value():
                self._changed(changed_sect, optname)
        # Options in any section and ${sectname:optname} interpolation.
        for sectname, sect in self.sections.items():
            for optname, option in sect.items():
                if ('${' + changed_sect + ':' + changed_opt + '}' in
                        option.value()):
                    self._changed(sectname, optname)

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
            raise configexc.NoSectionError(sectname)
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
        if not self._initialized:
            raise Exception("get got called before initialisation was "
                            "complete!")
        try:
            sect = self.sections[sectname]
        except KeyError:
            raise configexc.NoSectionError(sectname)
        try:
            val = sect[optname]
        except KeyError:
            raise configexc.NoOptionError(optname, sectname)
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
    def set_command(self, win_id: {'special': 'win_id'},
                    sectname: {'name': 'section'}=None,
                    optname: {'name': 'option'}=None, value=None, temp=False):
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
        if sectname is not None and optname is None:
            raise cmdexc.CommandError(
                "set: Either both section and option have to be given, or "
                "neither!")
        if sectname is None and optname is None:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            tabbed_browser.openurl(QUrl('qute:settings'), newtab=False)
            return
        try:
            if optname.endswith('?'):
                val = self.get(sectname, optname[:-1], transformed=False)
                message.info(win_id, "{} {} = {}".format(
                    sectname, optname[:-1], val), immediately=True)
            else:
                if value is None:
                    raise cmdexc.CommandError("set: The following arguments "
                                              "are required: value")
                layer = 'temp' if temp else 'conf'
                self.set(layer, sectname, optname, value)
        except (configexc.Error, configparser.Error) as e:
            raise cmdexc.CommandError("set: {} - {}".format(
                e.__class__.__name__, e))

    def set(self, layer, sectname, optname, value, validate=True):
        """Set an option.

        Args:
            layer: A layer name as string (conf/temp/default).
            sectname: The name of the section to change.
            optname: The name of the option to change.
            value: The new value.
            validate: Whether to validate the value immediately.
        """
        try:
            value = self._interpolation.before_set(self, sectname, optname,
                                                   value)
        except ValueError as e:
            raise configexc.InterpolationSyntaxError(optname, sectname, str(e))
        try:
            sect = self.sections[sectname]
        except KeyError:
            raise configexc.NoSectionError(sectname)
        mapping = {key: val.value() for key, val in sect.values.items()}
        if validate:
            interpolated = self._interpolation.before_get(
                self, sectname, optname, value, mapping)
        else:
            interpolated = None
        try:
            sect.setv(layer, optname, value, interpolated)
        except KeyError:
            raise configexc.NoOptionError(optname, sectname)
        else:
            if self._initialized:
                self._after_set(sectname, optname)

    @cmdutils.register(instance='config', name='save')
    def save_command(self):
        """Save the config file."""
        try:
            self.save()
        except OSError as e:
            raise cmdexc.CommandError("Could not save config: {}".format(e))

    def save(self):
        """Save the config file."""
        if self._configdir is None:
            return
        configfile = os.path.join(self._configdir, self._fname)
        log.destroy.debug("Saving config to {}".format(configfile))
        with qtutils.savefile_open(configfile) as f:
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
        return utils.get_repr(self, name=self.name)

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
