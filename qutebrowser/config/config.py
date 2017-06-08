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

"""Configuration storage and config-related utilities.

This borrows a lot of ideas from configparser, but also has some things that
are fundamentally different. This is why nothing inherits from configparser,
but we borrow some methods and classes from there where it makes sense.
"""

import re
import os
import sys
import os.path
import functools
import configparser
import contextlib
import collections
import collections.abc

from PyQt5.QtCore import pyqtSignal, QObject, QUrl, QSettings
from PyQt5.QtGui import QColor

from qutebrowser.config import configdata, configexc, textwrapper
from qutebrowser.config.parsers import keyconf
from qutebrowser.config.parsers import ini
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.utils import (message, objreg, utils, standarddir, log,
                               qtutils, error, usertypes)
from qutebrowser.misc import objects
from qutebrowser.utils.usertypes import Completion


UNSET = object()


class change_filter:  # pylint: disable=invalid-name

    """Decorator to filter calls based on a config section/option matching.

    This could also be a function, but as a class (with a "wrong" name) it's
    much cleaner to implement.

    Attributes:
        _sectname: The section to be filtered.
        _optname: The option to be filtered.
        _function: Whether a function rather than a method is decorated.
    """

    def __init__(self, sectname, optname=None, function=False):
        """Save decorator arguments.

        Gets called on parse-time with the decorator arguments.

        Args:
            sectname: The section to be filtered.
            optname: The option to be filtered.
            function: Whether a function rather than a method is decorated.
        """
        if sectname not in configdata.DATA:
            raise configexc.NoSectionError(sectname)
        if optname is not None and optname not in configdata.DATA[sectname]:
            raise configexc.NoOptionError(optname, sectname)
        self._sectname = sectname
        self._optname = optname
        self._function = function

    def __call__(self, func):
        """Filter calls to the decorated function.

        Gets called when a function should be decorated.

        Adds a filter which returns if we're not interested in the change-event
        and calls the wrapped function if we are.

        We assume the function passed doesn't take any parameters.

        Args:
            func: The function to be decorated.

        Return:
            The decorated function.
        """
        if self._function:
            @functools.wraps(func)
            def wrapper(sectname=None, optname=None):
                if sectname is None and optname is None:
                    # Called directly, not from a config change event.
                    return func()
                elif sectname != self._sectname:
                    return
                elif self._optname is not None and optname != self._optname:
                    return
                else:
                    return func()
        else:
            @functools.wraps(func)
            def wrapper(wrapper_self, sectname=None, optname=None):
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


def _init_main_config(parent=None):
    """Initialize the main config.

    Args:
        parent: The parent to pass to ConfigManager.
    """
    args = objreg.get('args')
    config_obj = ConfigManager(parent=parent)
    try:
        config_obj.read(standarddir.config(), 'qutebrowser.conf',
                        relaxed=args.relaxed_config)
    except (configexc.Error, configparser.Error, UnicodeDecodeError) as e:
        log.init.exception(e)
        errstr = "Error while reading config:"
        try:
            errstr += "\n\n{} -> {}:".format(
                e.section, e.option)
        except AttributeError:
            pass
        errstr += "\n"
        error.handle_fatal_exc(e, args, "Error while reading config!",
                               pre_text=errstr)
        # We didn't really initialize much so far, so we just quit hard.
        sys.exit(usertypes.Exit.err_config)
    else:
        objreg.register('config', config_obj)
        filename = os.path.join(standarddir.config(), 'qutebrowser.conf')
        save_manager = objreg.get('save-manager')
        save_manager.add_saveable(
            'config', config_obj.save, config_obj.changed,
            config_opt=('general', 'auto-save-config'), filename=filename)
        for sect in config_obj.sections.values():
            for opt in sect.values.values():
                if opt.values['conf'] is None:
                    # Option added to built-in defaults but not in user's
                    # config yet
                    save_manager.save('config', explicit=True, force=True)
                    return


def _init_key_config(parent):
    """Initialize the key config.

    Args:
        parent: The parent to use for the KeyConfigParser.
    """
    args = objreg.get('args')
    try:
        key_config = keyconf.KeyConfigParser(standarddir.config(), 'keys.conf',
                                             args.relaxed_config,
                                             parent=parent)
    except (keyconf.KeyConfigError, cmdexc.CommandError,
            UnicodeDecodeError) as e:
        log.init.exception(e)
        errstr = "Error while reading key config:\n"
        if e.lineno is not None:
            errstr += "In line {}: ".format(e.lineno)
        error.handle_fatal_exc(e, args, "Error while reading key config!",
                               pre_text=errstr)
        # We didn't really initialize much so far, so we just quit hard.
        sys.exit(usertypes.Exit.err_key_config)
    else:
        objreg.register('key-config', key_config)
        save_manager = objreg.get('save-manager')
        filename = os.path.join(standarddir.config(), 'keys.conf')
        save_manager.add_saveable(
            'key-config', key_config.save, key_config.config_dirty,
            config_opt=('general', 'auto-save-config'), filename=filename,
            dirty=key_config.is_dirty)


def _init_misc():
    """Initialize misc. config-related files."""
    save_manager = objreg.get('save-manager')
    state_config = ini.ReadWriteConfigParser(standarddir.data(), 'state')
    for sect in ['general', 'geometry']:
        try:
            state_config.add_section(sect)
        except configparser.DuplicateSectionError:
            pass
    # See commit a98060e020a4ba83b663813a4b9404edb47f28ad.
    state_config['general'].pop('fooled', None)
    objreg.register('state-config', state_config)
    save_manager.add_saveable('state-config', state_config.save)

    # We need to import this here because lineparser needs config.
    from qutebrowser.misc import lineparser
    command_history = lineparser.LimitLineParser(
        standarddir.data(), 'cmd-history',
        limit=('completion', 'cmd-history-max-items'),
        parent=objreg.get('config'))
    objreg.register('command-history', command_history)
    save_manager.add_saveable('command-history', command_history.save,
                              command_history.changed)

    # Set the QSettings path to something like
    # ~/.config/qutebrowser/qsettings/qutebrowser/qutebrowser.conf so it
    # doesn't overwrite our config.
    #
    # This fixes one of the corruption issues here:
    # https://github.com/qutebrowser/qutebrowser/issues/515

    path = os.path.join(standarddir.config(), 'qsettings')
    for fmt in [QSettings.NativeFormat, QSettings.IniFormat]:
        QSettings.setPath(fmt, QSettings.UserScope, path)


def init(parent=None):
    """Initialize the config.

    Args:
        parent: The parent to pass to QObjects which get initialized.
    """
    _init_main_config(parent)
    _init_key_config(parent)
    _init_misc()


def _get_value_transformer(mapping):
    """Get a function which transforms a value for CHANGED_OPTIONS.

    Args:
        mapping: A dictionary mapping old values to new values. Value is not
                 transformed if the supplied value doesn't match the old value.

    Return:
        A function which takes a value and transforms it.
    """
    def transformer(val):
        try:
            return mapping[val]
        except KeyError:
            return val
    return transformer


def _transform_position(val):
    """Transformer for position values."""
    mapping = {
        'north': 'top',
        'south': 'bottom',
        'west': 'left',
        'east': 'right',
    }
    try:
        return mapping[val]
    except KeyError:
        return val


def _transform_hint_color(val):
    """Transformer for hint colors."""
    log.config.debug("Transforming hint value {}".format(val))

    def to_rgba(qcolor):
        """Convert a QColor to a rgba() value."""
        return 'rgba({}, {}, {}, 0.8)'.format(qcolor.red(), qcolor.green(),
                                              qcolor.blue())

    if val.startswith('-webkit-gradient'):
        pattern = re.compile(r'-webkit-gradient\(linear, left top, '
                             r'left bottom, '
                             r'color-stop\(0%, *([^)]*)\), '
                             r'color-stop\(100%, *([^)]*)\)\)')

        match = pattern.fullmatch(val)
        if match:
            log.config.debug('Color groups: {}'.format(match.groups()))
            start_color = QColor(match.group(1))
            stop_color = QColor(match.group(2))
            if not start_color.isValid() or not stop_color.isValid():
                return None

            return ('qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {}, '
                    'stop:1 {})'.format(to_rgba(start_color),
                                        to_rgba(stop_color)))
        else:
            return None
    elif val.startswith('-'):  # Custom CSS stuff?
        return None
    else:  # Already transformed or a named color.
        return val


def _transform_hint_font(val):
    """Transformer for fonts -> hints."""
    match = re.fullmatch(r'(.*\d+p[xt]) Monospace', val)
    if match:
        # Close enough to the old default:
        return match.group(1) + ' ${_monospace}'
    else:
        return val


class ConfigManager(QObject):

    """Configuration manager for qutebrowser.

    Class attributes:
        KEY_ESCAPE: Chars which need escaping when they occur as first char
                    in a line.
        ESCAPE_CHAR: The char to be used for escaping
        RENAMED_SECTIONS: A mapping of renamed sections, {'oldname': 'newname'}
        RENAMED_OPTIONS: A mapping of renamed options,
                         {('section', 'oldname'): 'newname'}
        CHANGED_OPTIONS: A mapping of arbitrarily changed options,
                         {('section', 'option'): callable}.
                         The callable takes the old value and returns the new
                         one.
        DELETED_OPTIONS: A (section, option) list of deleted options.

    Attributes:
        sections: The configuration data as an OrderedDict.
        _fname: The filename to be opened.
        _configdir: The dictionary to read the config from and save it in.
        _interpolation: A configparser.Interpolation object
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
        ('colors', 'tab.fg.selected'): 'tabs.fg.selected.odd',
        ('colors', 'tabs.fg.selected'): 'tabs.fg.selected.odd',
        ('colors', 'tab.bg.odd'): 'tabs.bg.odd',
        ('colors', 'tab.bg.even'): 'tabs.bg.even',
        ('colors', 'tab.bg.selected'): 'tabs.bg.selected.odd',
        ('colors', 'tabs.bg.selected'): 'tabs.bg.selected.odd',
        ('colors', 'tab.bg.bar'): 'tabs.bg.bar',
        ('colors', 'tab.indicator.start'): 'tabs.indicator.start',
        ('colors', 'tab.indicator.stop'): 'tabs.indicator.stop',
        ('colors', 'tab.indicator.error'): 'tabs.indicator.error',
        ('colors', 'tab.indicator.system'): 'tabs.indicator.system',
        ('completion', 'history-length'): 'cmd-history-max-items',
        ('colors', 'downloads.fg'): 'downloads.fg.start',
        ('ui', 'show-keyhints'): 'keyhint-blacklist',
        ('content', 'javascript-can-open-windows'):
            'javascript-can-open-windows-automatically',
        ('colors', 'statusbar.fg.error'): 'messages.fg.error',
        ('colors', 'statusbar.bg.error'): 'messages.bg.error',
        ('colors', 'statusbar.fg.warning'): 'messages.fg.warning',
        ('colors', 'statusbar.bg.warning'): 'messages.bg.warning',
        ('colors', 'statusbar.fg.prompt'): 'prompts.fg',
        ('colors', 'statusbar.bg.prompt'): 'prompts.bg',
        ('storage', 'offline-web-application-storage'):
            'offline-web-application-cache',
    }
    DELETED_OPTIONS = [
        ('colors', 'tab.separator'),
        ('colors', 'tabs.separator'),
        ('colors', 'tab.seperator'),  # pragma: no spellcheck
        ('colors', 'tabs.seperator'),  # pragma: no spellcheck
        ('colors', 'completion.item.bg'),
        ('tabs', 'indicator-space'),
        ('tabs', 'hide-auto'),
        ('tabs', 'auto-hide'),
        ('tabs', 'hide-always'),
        ('ui', 'display-statusbar-messages'),
        ('ui', 'hide-mouse-cursor'),
        ('ui', 'css-media-type'),
        ('general', 'wrap-search'),
        ('general', 'site-specific-quirks'),
        ('hints', 'opacity'),
        ('completion', 'auto-open'),
        ('storage', 'object-cache-capacities'),
        ('storage', 'offline-storage-database'),
        ('storage', 'offline-storage-default-quota'),
        ('storage', 'offline-web-application-cache-quota'),
        ('content', 'css-regions'),
    ]
    CHANGED_OPTIONS = {
        ('content', 'cookies-accept'):
            _get_value_transformer({'default': 'no-3rdparty'}),
        ('tabs', 'new-tab-position'):
            _get_value_transformer({
                'left': 'prev',
                'right': 'next'}),
        ('tabs', 'new-tab-position-explicit'):
            _get_value_transformer({
                'left': 'prev',
                'right': 'next'}),
        ('tabs', 'position'): _transform_position,
        ('tabs', 'select-on-remove'):
            _get_value_transformer({
                'left': 'prev',
                'right': 'next',
                'previous': 'last-used'}),
        ('ui', 'downloads-position'): _transform_position,
        ('ui', 'remove-finished-downloads'):
            _get_value_transformer({'false': '-1', 'true': '1000'}),
        ('general', 'log-javascript-console'):
            _get_value_transformer({'false': 'none', 'true': 'debug'}),
        ('ui', 'keyhint-blacklist'):
            _get_value_transformer({'false': '*', 'true': ''}),
        ('hints', 'auto-follow'):
            _get_value_transformer({'false': 'never', 'true': 'unique-match'}),
        ('colors', 'hints.bg'): _transform_hint_color,
        ('colors', 'hints.fg'): _transform_hint_color,
        ('colors', 'hints.fg.match'): _transform_hint_color,
        ('fonts', 'hints'): _transform_hint_font,
        ('completion', 'show'):
            _get_value_transformer({'false': 'never', 'true': 'always'}),
        ('ui', 'user-stylesheet'):
            _get_value_transformer({
                'html > ::-webkit-scrollbar { width: 0px; height: 0px; }': '',
                '::-webkit-scrollbar { width: 0px; height: 0px; }': '',
            }),
        ('general', 'default-encoding'):
            _get_value_transformer({'': 'iso-8859-1'}),
        ('contents', 'cache-size'):
            _get_value_transformer({'52428800': ''}),
        ('storage', 'maximum-pages-in-cache'):
            _get_value_transformer({'': '0'}),
        ('fonts', 'web-size-minimum'):
            _get_value_transformer({'': '0'}),
        ('fonts', 'web-size-minimum-logical'):
            _get_value_transformer({'': '6'}),
        ('fonts', 'web-size-default'):
            _get_value_transformer({'': '16'}),
        ('fonts', 'web-size-default-fixed'):
            _get_value_transformer({'': '13'}),
    }

    changed = pyqtSignal(str, str)
    style_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initialized = False
        self._configdir = None
        self._fname = None
        self.sections = configdata.data()
        self._interpolation = configparser.ExtendedInterpolation()
        self._proxies = {}
        for sectname in self.sections:
            self._proxies[sectname] = SectionProxy(self, sectname)

    def __getitem__(self, key):
        """Get a section from the config."""
        return self._proxies[key]

    def __repr__(self):
        return utils.get_repr(self, fname=self._fname)

    def __str__(self):
        """Get the whole config as a string."""
        lines = configdata.FIRST_COMMENT.strip('\n').splitlines()
        for sectname, sect in self.sections.items():
            lines += ['\n'] + self._str_section_desc(sectname)
            lines.append('[{}]'.format(sectname))
            lines += self._str_items(sectname, sect)
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

    def _str_items(self, sectname, sect):
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
            lines += self._str_option_desc(sectname, sect, optname, option)
            lines.append(keyval)
        return lines

    def _str_option_desc(self, sectname, sect, optname, option):
        """Get the option description strings for a single option."""
        wrapper = textwrapper.TextWrapper(initial_indent='#' + ' ' * 5,
                                          subsequent_indent='#' + ' ' * 5)
        lines = []
        if not getattr(sect, 'descriptions', None):
            return lines

        lines.append('')
        typestr = ' ({})'.format(option.typ.get_name())
        lines.append("# {}{}:".format(optname, typestr))

        try:
            desc = self.sections[sectname].descriptions[optname]
        except KeyError:
            log.config.exception("No description for {}.{}!".format(
                sectname, optname))
            return []
        for descline in desc.splitlines():
            lines += wrapper.wrap(descline)
        valid_values = option.typ.get_valid_values()
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

    def _from_cp(self, cp, relaxed=False):
        """Read the config from a configparser instance.

        Args:
            cp: The configparser instance to read the values from.
            relaxed: Whether to ignore inexistent sections/options.
        """
        for sectname in cp:
            if sectname in self.RENAMED_SECTIONS:
                sectname = self.RENAMED_SECTIONS[sectname]
            if sectname != 'DEFAULT' and sectname not in self.sections:
                if not relaxed:
                    raise configexc.NoSectionError(sectname)
        for sectname in self.sections:
            self._from_cp_section(sectname, cp, relaxed)

    def _from_cp_section(self, sectname, cp, relaxed):
        """Read a single section from a configparser instance.

        Args:
            sectname: The name of the section to read.
            cp: The configparser instance to read the values from.
            relaxed: Whether to ignore inexistent options.
        """
        real_sectname = self._get_real_sectname(cp, sectname)
        if real_sectname is None:
            return
        for k, v in cp[real_sectname].items():
            if k.startswith(self.ESCAPE_CHAR):
                k = k[1:]

            if (sectname, k) in self.DELETED_OPTIONS:
                continue
            if (sectname, k) in self.RENAMED_OPTIONS:
                k = self.RENAMED_OPTIONS[sectname, k]
            if (sectname, k) in self.CHANGED_OPTIONS:
                func = self.CHANGED_OPTIONS[(sectname, k)]
                new_v = func(v)
                if new_v is None:
                    exc = configexc.ValidationError(
                        v, "Could not automatically migrate the given value")
                    exc.section = sectname
                    exc.option = k
                    raise exc

                v = new_v

            try:
                self.set('conf', sectname, k, v, validate=False)
            except configexc.NoOptionError:
                if relaxed:
                    pass
                else:
                    raise

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
        log.config.debug("Config option changed: {} -> {}".format(
            sectname, optname))
        if sectname in ['colors', 'fonts']:
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

    def read(self, configdir, fname, relaxed=False):
        """Read the config from the given directory/file."""
        self._fname = fname
        self._configdir = configdir
        parser = ini.ReadConfigParser(configdir, fname)
        self._from_cp(parser, relaxed)
        self._initialized = True
        self._validate_all()

    def items(self, sectname, raw=True):
        """Get a list of (optname, value) tuples for a section.

        Implemented for configparser interpolation compatibility

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
            sectdict.delete(optname)
            self.get.cache_clear()
        return existed

    @functools.lru_cache()
    def get(self, sectname, optname, raw=False, transformed=True,
            fallback=UNSET):
        """Get the value from a section/option.

        We don't support the vars argument from configparser.get as it's not
        hashable.

        Args:
            sectname: The section to get the option from.
            optname: The option name
            raw: Whether to get the uninterpolated, untransformed value.
            transformed: Whether the value should be transformed.

        Return:
            The value of the option.
        """
        if not self._initialized:
            raise Exception("get got called before initialization was "
                            "complete!")

        try:
            sect = self.sections[sectname]
        except KeyError:
            if fallback is not UNSET:
                return fallback
            raise configexc.NoSectionError(sectname)
        try:
            val = sect[optname]
        except KeyError:
            if fallback is not UNSET:
                return fallback
            raise configexc.NoOptionError(optname, sectname)
        if raw:
            return val.value()
        mapping = {key: val.value() for key, val in sect.values.items()}
        newval = self._interpolation.before_get(self, sectname, optname,
                                                val.value(), mapping)
        if transformed:
            newval = val.typ.transform(newval)
        return newval

    @contextlib.contextmanager
    def _handle_config_error(self):
        """Catch errors in set_command and raise CommandError."""
        try:
            yield
        except (configexc.NoOptionError, configexc.NoSectionError,
                configexc.ValidationError) as e:
            raise cmdexc.CommandError("set: {}".format(e))
        except (configexc.Error, configparser.Error) as e:
            raise cmdexc.CommandError("set: {} - {}".format(
                e.__class__.__name__, e))

    @cmdutils.register(name='set', instance='config', star_args_optional=True)
    @cmdutils.argument('section_', completion=Completion.section)
    @cmdutils.argument('option', completion=Completion.option)
    @cmdutils.argument('values', completion=Completion.value)
    @cmdutils.argument('win_id', win_id=True)
    def set_command(self, win_id, section_=None, option=None, *values,
                    temp=False, print_=False):
        """Set an option.

        If the option name ends with '?', the value of the option is shown
        instead.

        If the option name ends with '!' and it is a boolean value, toggle it.

        //

        Wrapper for self.set() to output exceptions in the status bar.

        Args:
            section_: The section where the option is in.
            option: The name of the option.
            values: The value to set, or the values to cycle through.
            temp: Set value temporarily.
            print_: Print the value after setting.
        """
        if section_ is not None and option is None:
            raise cmdexc.CommandError(
                "set: Either both section and option have to be given, or "
                "neither!")
        if section_ is None and option is None:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            tabbed_browser.openurl(QUrl('qute://settings'), newtab=False)
            return

        if option.endswith('?') and option != '?':
            option = option[:-1]
            print_ = True
        else:
            with self._handle_config_error():
                if option.endswith('!') and option != '!' and not values:
                    # Handle inversion as special cases of the cycle code path
                    option = option[:-1]
                    val = self.get(section_, option)
                    if isinstance(val, bool):
                        values = ['false', 'true']
                    else:
                        raise cmdexc.CommandError(
                            "set: Attempted inversion of non-boolean value.")
                elif not values:
                    raise cmdexc.CommandError("set: The following arguments "
                                              "are required: value")

                layer = 'temp' if temp else 'conf'
                self._set_next(layer, section_, option, values)

        if print_:
            with self._handle_config_error():
                val = self.get(section_, option, transformed=False)
            message.info("{} {} = {}".format(section_, option, val))

    def _set_next(self, layer, section_, option, values):
        """Set the next value out of a list of values."""
        if len(values) == 1:
            # If we have only one value, just set it directly (avoid
            # breaking stuff like aliases or other pseudo-settings)
            self.set(layer, section_, option, values[0])
        else:
            # Otherwise, use the next valid value from values, or the
            # first if the current value does not appear in the list
            assert len(values) > 1
            val = self.get(section_, option, transformed=False)
            try:
                idx = values.index(str(val))
                idx = (idx + 1) % len(values)
                value = values[idx]
            except ValueError:
                value = values[0]
            self.set(layer, section_, option, value)

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
            try:
                allowed_backends = sect.values[optname].backends
            except KeyError:
                # Will be handled later in .setv()
                pass
            else:
                if (allowed_backends is not None and
                        objects.backend not in allowed_backends):
                    raise configexc.BackendError(objects.backend)
        else:
            interpolated = None

        try:
            sect.setv(layer, optname, value, interpolated)
        except KeyError:
            raise configexc.NoOptionError(optname, sectname)
        else:
            if self._initialized:
                self._after_set(sectname, optname)

    def save(self):
        """Save the config file."""
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
