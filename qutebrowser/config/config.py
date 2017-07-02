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

import copy
import os.path
import contextlib
import functools

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QUrl

from qutebrowser.config import configdata, configexc, configtypes, configfiles
from qutebrowser.utils import (utils, objreg, message, standarddir, log,
                               usertypes, jinja)
from qutebrowser.commands import cmdexc, cmdutils, runners


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


class KeyConfig:

    """Utilities related to keybindings.

    Note that the actual values are saved in the config itself, not here.

    Attributes:
        _config: The Config object to be used.
    """

    def __init__(self, config):
        self._config = config

    def get_bindings_for(self, mode):
        """Get the combined bindings for the given mode."""
        bindings = dict(val.bindings.default[mode])
        for key, binding in val.bindings.commands[mode].items():
            if binding is None:
                bindings.pop(key, None)
            else:
                bindings[key] = binding
        return bindings

    def get_reverse_bindings_for(self, mode):
        """Get a dict of commands to a list of bindings for the mode."""
        cmd_to_keys = {}
        bindings = self.get_bindings_for(mode)
        for key, full_cmd in sorted(bindings.items()):
            for cmd in full_cmd.split(';;'):
                cmd = cmd.strip()
                cmd_to_keys.setdefault(cmd, [])
                # put special bindings last
                if utils.is_special_key(key):
                    cmd_to_keys[cmd].append(key)
                else:
                    cmd_to_keys[cmd].insert(0, key)
        return cmd_to_keys

    def _prepare(self, key, mode):
        """Make sure the given mode exists and normalize the key."""
        if mode not in configdata.DATA['bindings.default'].default:
            raise configexc.KeybindingError("Invalid mode {}!".format(mode))
        if utils.is_special_key(key):
            # <Ctrl-t>, <ctrl-T>, and <ctrl-t> should be considered equivalent
            return utils.normalize_keystr(key)
        return key

    def bind(self, key, command, *, mode, force=False, save_yaml=False):
        """Add a new binding from key to command."""
        key = self._prepare(key, mode)

        parser = runners.CommandParser()
        try:
            results = parser.parse_all(command)
        except cmdexc.Error as e:
            raise configexc.KeybindingError("Invalid command: {}".format(e))

        for result in results:
            try:
                result.cmd.validate_mode(usertypes.KeyMode[mode])
            except cmdexc.PrerequisitesError as e:
                raise configexc.KeybindingError(str(e))

        log.keyboard.vdebug("Adding binding {} -> {} in mode {}.".format(
            key, command, mode))
        if key in self.get_bindings_for(mode) and not force:
            raise configexc.DuplicateKeyError(key)

        bindings = self._config.get_obj('bindings.commands')
        if mode not in bindings:
            bindings[mode] = {}
        bindings[mode][key] = command
        self._config.update_mutables(save_yaml=save_yaml)

    def unbind(self, key, *, mode='normal', save_yaml=False):
        """Unbind the given key in the given mode."""
        key = self._prepare(key, mode)

        bindings_commands = self._config.get_obj('bindings.commands')

        if key in val.bindings.commands[mode]:
            # In custom bindings -> remove it
            del bindings_commands[mode][key]
        elif key in val.bindings.default[mode]:
            # In default bindings -> shadow it with None
            if mode not in bindings_commands:
                bindings_commands[mode] = {}
            bindings_commands[mode][key] = None
        else:
            raise configexc.KeybindingError("Can't find binding '{}' in section '{}'!"
                                            .format(key, mode))

        self._config.update_mutables(save_yaml=save_yaml)

    def get_command(self, key, mode):
        """Get the command for a given key (or None)."""
        key = self._prepare(key, mode)
        return val.bindings.commands[mode].get(key, None)


class ConfigCommands:

    """qutebrowser commands related to the configuration."""

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
                if isinstance(opt.typ, configtypes.Bool):
                    values = ['false', 'true']
                else:
                    raise cmdexc.CommandError(
                        "set: Attempted inversion of non-boolean value.")
            elif not values:
                raise cmdexc.CommandError("set: The following arguments "
                                          "are required: value")
            self._set_next(option, values, temp=temp)

        if print_:
            self._print_value(option)

    def _print_value(self, option):
        """Print the value of the given option."""
        with self._handle_config_error():
            val = self._config.get_str(option)
        message.info("{} = {}".format(option, val))

    def _set_next(self, option, values, *, temp):
        """Set the next value out of a list of values."""
        if len(values) == 1:
            # If we have only one value, just set it directly (avoid
            # breaking stuff like aliases or other pseudo-settings)
            self._config.set_str(option, values[0], save_yaml=not temp)
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
        self._config.set_str(option, value, save_yaml=not temp)

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

    @cmdutils.register(instance='config-commands', maxsplit=1,
                       no_cmd_split=True, no_replace_variables=True)
    @cmdutils.argument('command', completion=usertypes.Completion.bind)
    def bind(self, key, command=None, *, mode='normal', force=False):
        """Bind a key to a command.

        Args:
            key: The keychain or special key (inside `<...>`) to bind.
            command: The command to execute, with optional args, or None to
                     print the current binding.
            mode: A comma-separated list of modes to bind the key in
                  (default: `normal`).
            force: Rebind the key if it is already bound.
        """
        if command is None:
            if utils.is_special_key(key):
                # key_instance.get_command does this, but we also need it
                # normalized for the output below
                key = utils.normalize_keystr(key)
            cmd = key_instance.get_command(key, mode)
            if cmd is None:
                message.info("{} is unbound in {} mode".format(key, mode))
            else:
                message.info("{} is bound to '{}' in {} mode".format(
                    key, cmd, mode))
            return

        try:
            key_instance.bind(key, command, mode=mode, force=force,
                              save_yaml=True)
        except configexc.DuplicateKeyError as e:
            raise cmdexc.CommandError(str(e) + " - use --force to override!")
        except configexc.KeybindingError as e:
            raise cmdexc.CommandError(str(e))

    @cmdutils.register(instance='config-commands')
    def unbind(self, key, mode='normal'):
        """Unbind a keychain.

        Args:
            key: The keychain or special key (inside <...>) to unbind.
            mode: A mode to unbind the key in (default: `normal`).
        """
        try:
            key_instance.unbind(key, mode=mode, save_yaml=True)
        except configexc.KeybindingError as e:
            raise cmdexc.CommandError(str(e))


class Config(QObject):

    """Main config object.

    Attributes:
        options: A dict mapping setting names to configdata.Option objects.
                 Those contain the type, default value, etc.
        _values: A dict mapping setting names to their values.
        _mutables: A list of mutable objects to be checked for changes.
        _yaml: A YamlConfig object or None.

    Signals:
        changed: Emitted with the option name when an option changed.
    """

    changed = pyqtSignal(str)

    def __init__(self, yaml_config, parent=None):
        super().__init__(parent)
        self.options = {}
        self._values = {}
        self._mutables = []
        self._yaml = yaml_config

    def _changed(self, name, value):
        """Emit changed signal and log change."""
        self.changed.emit(name)
        log.config.debug("Config option changed: {} = {}".format(name, value))

    def read_configdata(self):
        """Read the option objects from configdata."""
        for name, option in configdata.DATA.items():
            self.options[name] = option

    def read_yaml(self):
        """Read the YAML settings from self._yaml."""
        self._yaml.load()
        for name, value in self._yaml.values.items():
            opt = self.get_opt(name)
            opt.typ.to_py(value)  # for validation
            self._values[name] = value

    def get_opt(self, name):
        """Get a configdata.Option object for the given setting."""
        try:
            return self.options[name]
        except KeyError:
            raise configexc.NoOptionError(name)

    def get(self, name):
        """Get the given setting converted for Python code."""
        opt = self.get_opt(name)
        obj = self.get_obj(name, mutable=False)
        return opt.typ.to_py(obj)

    def get_obj(self, name, *, mutable=True):
        """Get the given setting as object (for YAML/config.py).

        If mutable=True is set, watch the returned object for mutations.
        """
        opt = self.get_opt(name)
        obj = self._values.get(name, opt.default)
        if isinstance(obj, (dict, list)):
            if mutable:
                self._mutables.append((name, copy.deepcopy(obj), obj))
        else:
            # Shouldn't be mutable (and thus hashable)
            assert obj.__hash__ is not None, obj
        return obj

    def get_str(self, name):
        """Get the given setting as string."""
        opt = self.get_opt(name)
        value = self._values.get(name, opt.default)
        return opt.typ.to_str(value)

    def set_obj(self, name, value, *, save_yaml=False):
        """Set the given setting from a YAML/config.py object.

        If save_yaml=True is given, store the new value to YAML.
        """
        opt = self.get_opt(name)
        opt.typ.to_py(value)  # for validation
        self._values[name] = value
        self._changed(name, value)
        if save_yaml:
            self._yaml.values[name] = value

    def set_str(self, name, value, *, save_yaml=False):
        """Set the given setting from a string.

        If save_yaml=True is given, store the new value to YAML.
        """
        opt = self.get_opt(name)
        converted = opt.typ.from_str(value)
        self._values[name] = converted
        self._changed(name, converted)
        if save_yaml:
            self._yaml.values[name] = converted

    def update_mutables(self, *, save_yaml=False):
        """Update mutable settings if they changed.

        Every time someone calls get_obj() on a mutable object, we save a
        reference to the original object and a copy.

        Here, we check all those saved copies for mutations, and if something
        mutated, we call set_obj again so we save the new value.
        """
        for name, old_value, new_value in self._mutables:
            if old_value != new_value:
                log.config.debug("{} was mutated, updating".format(name))
                self.set_obj(name, new_value, save_yaml=save_yaml)
        self._mutables = []

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
        _config: The Config object.
        _prefix: The __getattr__ chain leading up to this object.
    """

    def __init__(self, config, prefix=''):
        self._config = config
        self._prefix = prefix

    def __repr__(self):
        return utils.get_repr(self, constructor=True, config=self._config,
                              prefix=self._prefix)

    def __getattr__(self, attr):
        """Get an option or a new ConfigContainer with the added prefix.

        If we get an option which exists, we return the value for it.
        If we get a part of an option name, we return a new ConfigContainer.

        Those two never overlap as configdata.py ensures there are no shadowing
        options.
        """
        if attr.startswith('_'):
            return self.__getattribute__(attr)

        name = self._join(attr)
        if configdata.is_valid_prefix(name):
            return ConfigContainer(config=self._config, prefix=name)

        try:
            return self._config.get(name)
        except configexc.NoOptionError as e:
            # If it's not a valid prefix - re-raise to improve error text.
            raise configexc.NoOptionError(name)

    def __setattr__(self, attr, value):
        """Set the given option in the config."""
        if attr.startswith('_'):
            return super().__setattr__(attr, value)
        self._config.set_obj(self._join(attr), value)

    def _join(self, attr):
        """Get the prefix joined with the given attribute."""
        if self._prefix:
            return '{}.{}'.format(self._prefix, attr)
        else:
            return attr


def set_register_stylesheet(obj, *, stylesheet=None, update=True):
    """Set the stylesheet for an object based on it's STYLESHEET attribute.

    Also, register an update when the config is changed.

    Args:
        obj: The object to set the stylesheet for and register.
             Must have a STYLESHEET attribute if stylesheet is not given.
        stylesheet: The stylesheet to use.
        update: Whether to update the stylesheet on config changes.
    """
    observer = StyleSheetObserver(obj, stylesheet=stylesheet)
    observer.register(update=update)


class StyleSheetObserver(QObject):

    """Set the stylesheet on the given object and update it on changes.

    Attributes:
        _obj: The object to observe.
        _stylesheet: The stylesheet template to use.
    """

    def __init__(self, obj, stylesheet):
        super().__init__(parent=obj)
        self._obj = obj
        if stylesheet is None:
            self._stylesheet = obj.STYLESHEET
        else:
            self._stylesheet = stylesheet

    def _get_stylesheet(self):
        """Format a stylesheet based on a template.

        Return:
            The formatted template as string.
        """
        template = jinja.environment.from_string(self._stylesheet)
        return template.render(conf=val)

    @pyqtSlot()
    def _update_stylesheet(self):
        """Update the stylesheet for obj."""
        self._obj.setStyleSheet(self._get_stylesheet())

    def register(self, update):
        """Do a first update and listen for more.

        Args:
            update: if False, don't listen for future updates.
        """
        qss = self._get_stylesheet()
        log.config.vdebug("stylesheet for {}: {}".format(
            self._obj.__class__.__name__, qss))
        self._obj.setStyleSheet(qss)
        if update:
            instance.changed.connect(self._update_stylesheet)


def init(parent=None):
    """Initialize the config.

    Args:
        parent: The parent to pass to QObjects which get initialized.
    """
    configdata.init()

    yaml_config = configfiles.YamlConfig()
    config = Config(yaml_config=yaml_config, parent=parent)
    config.read_configdata()
    objreg.register('config', config)

    config_commands = ConfigCommands(config)
    objreg.register('config-commands', config_commands)

    global val, instance, key_instance
    val = ConfigContainer(config)
    instance = config
    key_instance = KeyConfig(config)

    for cf in _change_filters:
        cf.validate()
    config.read_yaml()

    configfiles.init(instance)
