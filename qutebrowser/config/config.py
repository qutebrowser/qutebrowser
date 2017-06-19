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

"""Configuration storage and config-related utilities."""

import os.path
import contextlib
import functools
import configparser

from PyQt5.QtCore import pyqtSignal, QObject, QUrl, QSettings

from qutebrowser.config import configdata, configexc, configtypes
from qutebrowser.utils import utils, objreg, message, standarddir, log
from qutebrowser.commands import cmdexc, cmdutils


# An easy way to access the config from other code via config.val.foo
val = None
instance = None
key_instance = None

# Keeping track of all change filters to validate them later.
_change_filters = []


class change_filter:  # pylint: disable=invalid-name

    """Decorator to filter calls based on a config section/option matching.

    This could also be a function, but as a class (with a "wrong" name) it's
    much cleaner to implement.

    Attributes:
        _option: An option or prefix to be filtered
        _function: Whether a function rather than a method is decorated.
    """

    def __init__(self, option, function=False):
        """Save decorator arguments.

        Gets called on parse-time with the decorator arguments.

        Args:
            option: The option to be filtered.
            function: Whether a function rather than a method is decorated.
        """
        self._option = option
        self._function = function
        _change_filters.append(self)

    def validate(self):
        """Make sure the configured option or prefix exists.

        We can't do this in __init__ as configdata isn't ready yet.
        """
        if (self._option not in configdata.DATA and
                not configdata.is_valid_prefix(self._option)):
            raise configexc.NoOptionError(self._option)

    def _check_match(self, option):
        """Check if the given option matches the filter."""
        if option is None:
            # Called directly, not from a config change event.
            return True
        elif option == self._option:
            return True
        elif option.startswith(self._option + '.'):
            # prefix match
            return True
        else:
            return False

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
            def wrapper(option=None):
                if self._check_match(option):
                    return func()
        else:
            @functools.wraps(func)
            def wrapper(wrapper_self, option=None):
                if self._check_match(option):
                    return func(wrapper_self)

        return wrapper


class NewKeyConfig:

    def get_reverse_bindings_for(self, section):
        """Get a dict of commands to a list of bindings for the section."""
        cmd_to_keys = {}
        bindings = val.bindings.commands[section]
        if bindings is None:
            return cmd_to_keys
        for key, full_cmd in bindings.items():
            for cmd in full_cmd.split(';;'):
                cmd = cmd.strip()
                cmd_to_keys.setdefault(cmd, [])
                # put special bindings last
                if utils.is_special_key(key):
                    cmd_to_keys[cmd].append(key)
                else:
                    cmd_to_keys[cmd].insert(0, key)
        return cmd_to_keys


class ConfigCommands:

    def __init__(self, config):
        self._config = config

    @cmdutils.register(instance='config-commands', star_args_optional=True)
    @cmdutils.argument('win_id', win_id=True)
    def set(self, win_id, option=None, *values, temp=False, print_=False):
        """Set an option.

        If the option name ends with '?', the value of the option is shown
        instead.

        If the option name ends with '!' and it is a boolean value, toggle it.

        //

        Args:
            option: The name of the option.
            values: The value to set, or the values to cycle through.
            temp: Set value temporarily until qutebrowser is closed.
            print_: Print the value after setting.
        """
        # FIXME:conf write to YAML if temp isn't used!
        if option is None:
            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            tabbed_browser.openurl(QUrl('qute://settings'), newtab=False)
            return

        if option.endswith('?') and option != '?':
            self._print_value(option[:-1])
            return

        with self._handle_config_error():
            if option.endswith('!') and option != '!' and not values:
                # Handle inversion as special cases of the cycle code path
                option = option[:-1]
                opt = self._config.get_opt(option)
                if opt.typ is configtypes.Bool:
                    values = ['false', 'true']
                else:
                    raise cmdexc.CommandError(
                        "set: Attempted inversion of non-boolean value.")
            elif not values:
                raise cmdexc.CommandError("set: The following arguments "
                                          "are required: value")
            self._set_next(option, values)

        if print_:
            self._print_value(option)

    def _print_value(self, option):
        """Print the value of the given option."""
        with self._handle_config_error():
            val = self._config.get_str(option)
        message.info("{} = {}".format(option, val))

    def _set_next(self, option, values):
        """Set the next value out of a list of values."""
        if len(values) == 1:
            # If we have only one value, just set it directly (avoid
            # breaking stuff like aliases or other pseudo-settings)
            self._config.set(option, values[0])
            return

        # Use the next valid value from values, or the first if the current
        # value does not appear in the list
        val = self._config.get_str(option)
        try:
            idx = values.index(str(val))
            idx = (idx + 1) % len(values)
            value = values[idx]
        except ValueError:
            value = values[0]
        self._config.set(option, value)

    @contextlib.contextmanager
    def _handle_config_error(self):
        """Catch errors in set_command and raise CommandError."""
        try:
            yield
        except (configexc.NoOptionError, configexc.ValidationError) as e:
            raise cmdexc.CommandError("set: {}".format(e))
        except configexc.Error as e:
            raise cmdexc.CommandError("set: {} - {}".format(
                e.__class__.__name__, e))


class NewConfigManager(QObject):

    changed = pyqtSignal(str)  # FIXME:conf stub...

    def __init__(self, parent=None):
        super().__init__(parent)
        self.options = {}
        self._values = {}  # FIXME:conf stub

    def read_defaults(self):
        for name, option in configdata.DATA.items():
            self.options[name] = option

    def get_opt(self, name):
        try:
            return self.options[name]
        except KeyError:
            raise configexc.NoOptionError(name)

    def get(self, name):
        opt = self.get_opt(name)
        value = self._values.get(name, opt.default)
        return opt.typ.to_py(value)

    def get_str(self, name):
        opt = self.get_opt(name)
        value = self._values.get(name, opt.default)
        return opt.typ.to_str(value)

    def set(self, name, value):
        # FIXME:conf stub
        opt = self.get_opt(name)
        self._values[name] = opt.typ.from_str(value)
        self.changed.emit(name)
        log.config.debug("Config option changed: {} = {}".format(name, value))

    def dump_userconfig(self):
        """Get the part of the config which was changed by the user.

        Return:
            The changed config part as string.
        """
        lines = ['{} = {}'.format(optname, value)
                 for optname, value in self._values.items()]
        if not lines:
            lines = ['<Default configuration>']
        return '\n'.join(lines)


class ConfigContainer:

    """An object implementing config access via __getattr__.

    Attributes:
        _manager: The ConfigManager object.
        _prefix: The __getattr__ chain leading up to this object.
    """

    def __init__(self, manager, prefix=''):
        self._manager = manager
        self._prefix = prefix

    def __repr__(self):
        return utils.get_repr(self, constructor=True, manager=self._manager,
                              prefix=self._prefix)

    def __getattr__(self, attr):
        """Get an option or a new ConfigContainer with the added prefix.

        If we get an option which exists, we return the value for it.
        If we get a part of an option name, we return a new ConfigContainer.

        Those two never overlap as configdata.py ensures there are no shadowing
        options.
        """
        name = self._join(attr)
        if configdata.is_valid_prefix(name):
            return ConfigContainer(manager=self._manager, prefix=name)
        try:
            return self._manager.get(name)
        except configexc.NoOptionError as e:
            # If it's not a valid prefix - re-raise to improve error text.
            raise configexc.NoOptionError(name)

    def __setattr__(self, attr, value):
        if attr.startswith('_'):
            return super().__setattr__(attr, value)
        self._handler(self._join(attr), value)

    def _join(self, attr):
        if self._prefix:
            return '{}.{}'.format(self._prefix, attr)
        else:
            return attr


class StateConfig(configparser.ConfigParser):

    """The "state" file saving various application state."""

    def __init__(self):
        super().__init__()
        save_manager = objreg.get('save-manager')
        self._filename = os.path.join(standarddir.data(), 'state')
        self.read(self._filename, encoding='utf-8')
        for sect in ['general', 'geometry']:
            try:
                self.add_section(sect)
            except configparser.DuplicateSectionError:
                pass
        # See commit a98060e020a4ba83b663813a4b9404edb47f28ad.
        self['general'].pop('fooled', None)
        save_manager.add_saveable('state-config', self._save)

    def _save(self):
        """Save the state file to the configured location."""
        with open(self._filename, 'w', encoding='utf-8') as f:
            self.write(f)


def init(parent=None):
    """Initialize the config.

    Args:
        parent: The parent to pass to QObjects which get initialized.
    """
    configdata.init()

    new_config = NewConfigManager(parent)
    new_config.read_defaults()
    objreg.register('config', new_config)

    config_commands = ConfigCommands(new_config)
    objreg.register('config-commands', config_commands)

    global val, instance, key_instance
    val = ConfigContainer(new_config)
    instance = new_config
    key_instance = NewKeyConfig()

    for cf in _change_filters:
        cf.validate()

    state = StateConfig()
    objreg.register('state-config', state)

    # We need to import this here because lineparser needs config.
    # FIXME:conf add this to the Command widget or something?
    from qutebrowser.misc import lineparser
    save_manager = objreg.get('save-manager')
    command_history = lineparser.LimitLineParser(
        standarddir.data(), 'cmd-history',
        limit='completion.cmd_history_max_items',
        parent=instance)
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
