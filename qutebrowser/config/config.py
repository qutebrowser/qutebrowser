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
import contextlib
import functools

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject

from qutebrowser.config import configdata, configexc
from qutebrowser.utils import utils, log, jinja
from qutebrowser.misc import objects

# An easy way to access the config from other code via config.val.foo
val = None
instance = None
key_instance = None

# Keeping track of all change filters to validate them later.
change_filters = []


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
        change_filters.append(self)

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

    def _prepare(self, key, mode):
        """Make sure the given mode exists and normalize the key."""
        if mode not in configdata.DATA['bindings.default'].default:
            raise configexc.KeybindingError("Invalid mode {}!".format(mode))
        if utils.is_special_key(key):
            # <Ctrl-t>, <ctrl-T>, and <ctrl-t> should be considered equivalent
            return utils.normalize_keystr(key)
        return key

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

    def get_command(self, key, mode):
        """Get the command for a given key (or None)."""
        key = self._prepare(key, mode)
        bindings = self.get_bindings_for(mode)
        return bindings.get(key, None)

    def bind(self, key, command, *, mode, save_yaml=False):
        """Add a new binding from key to command."""
        if command is not None and not command.strip():
            raise configexc.KeybindingError(
                "Can't add binding '{}' with empty command in {} "
                'mode'.format(key, mode))

        key = self._prepare(key, mode)
        log.keyboard.vdebug("Adding binding {} -> {} in mode {}.".format(
            key, command, mode))

        bindings = self._config.get_obj('bindings.commands')
        if mode not in bindings:
            bindings[mode] = {}
        bindings[mode][key] = command
        self._config.update_mutables(save_yaml=save_yaml)

    def bind_default(self, key, *, mode='normal', save_yaml=False):
        """Restore a default keybinding."""
        key = self._prepare(key, mode)

        bindings_commands = self._config.get_obj('bindings.commands')
        try:
            del bindings_commands[mode][key]
        except KeyError:
            raise configexc.KeybindingError(
                "Can't find binding '{}' in {} mode".format(key, mode))
        self._config.update_mutables(save_yaml=save_yaml)

    def unbind(self, key, *, mode='normal', save_yaml=False):
        """Unbind the given key in the given mode."""
        key = self._prepare(key, mode)

        bindings_commands = self._config.get_obj('bindings.commands')

        if val.bindings.commands[mode].get(key, None) is not None:
            # In custom bindings -> remove it
            del bindings_commands[mode][key]
        elif key in val.bindings.default[mode]:
            # In default bindings -> shadow it with None
            if mode not in bindings_commands:
                bindings_commands[mode] = {}
            bindings_commands[mode][key] = None
        else:
            raise configexc.KeybindingError(
                "Can't find binding '{}' in {} mode".format(key, mode))

        self._config.update_mutables(save_yaml=save_yaml)


class Config(QObject):

    """Main config object.

    Attributes:
        _values: A dict mapping setting names to their values.
        _mutables: A dictionary of mutable objects to be checked for changes.
        _yaml: A YamlConfig object or None.

    Signals:
        changed: Emitted with the option name when an option changed.
    """

    changed = pyqtSignal(str)

    def __init__(self, yaml_config, parent=None):
        super().__init__(parent)
        self.changed.connect(_render_stylesheet.cache_clear)
        self._values = {}
        self._mutables = {}
        self._yaml = yaml_config

    def __iter__(self):
        """Iterate over Option, value tuples."""
        for name, value in sorted(self._values.items()):
            yield (self.get_opt(name), value)

    def init_save_manager(self, save_manager):
        """Make sure the config gets saved properly.

        We do this outside of __init__ because the config gets created before
        the save_manager exists.
        """
        self._yaml.init_save_manager(save_manager)

    def _set_value(self, opt, value):
        """Set the given option to the given value."""
        if not isinstance(objects.backend, objects.NoBackend):
            if objects.backend not in opt.backends:
                raise configexc.BackendError(objects.backend)

        opt.typ.to_py(value)  # for validation
        self._values[opt.name] = opt.typ.from_obj(value)

        self.changed.emit(opt.name)
        log.config.debug("Config option changed: {} = {}".format(
            opt.name, value))

    def read_yaml(self):
        """Read the YAML settings from self._yaml."""
        self._yaml.load()
        for name, value in self._yaml:
            self._set_value(self.get_opt(name), value)

    def get_opt(self, name):
        """Get a configdata.Option object for the given setting."""
        try:
            return configdata.DATA[name]
        except KeyError:
            deleted = name in configdata.MIGRATIONS.deleted
            renamed = configdata.MIGRATIONS.renamed.get(name)
            exception = configexc.NoOptionError(
                name, deleted=deleted, renamed=renamed)
            raise exception from None

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
        obj = None
        # If we allow mutation, there is a chance that prior mutations already
        # entered the mutable dictionary and thus further copies are unneeded
        # until update_mutables() is called
        if name in self._mutables and mutable:
            _copy, obj = self._mutables[name]
        # Otherwise, we return a copy of the value stored internally, so the
        # internal value can never be changed by mutating the object returned.
        else:
            obj = copy.deepcopy(self._values.get(name, opt.default))
            # Then we watch the returned object for changes.
            if isinstance(obj, (dict, list)):
                if mutable:
                    self._mutables[name] = (copy.deepcopy(obj), obj)
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
        self._set_value(self.get_opt(name), value)
        if save_yaml:
            self._yaml[name] = value

    def set_str(self, name, value, *, save_yaml=False):
        """Set the given setting from a string.

        If save_yaml=True is given, store the new value to YAML.
        """
        opt = self.get_opt(name)
        converted = opt.typ.from_str(value)
        log.config.debug("Setting {} (type {}) to {!r} (converted from {!r})"
                         .format(name, opt.typ.__class__.__name__, converted,
                                 value))
        self._set_value(opt, converted)
        if save_yaml:
            self._yaml[name] = converted

    def unset(self, name, *, save_yaml=False):
        """Set the given setting back to its default."""
        self.get_opt(name)
        try:
            del self._values[name]
        except KeyError:
            return
        self.changed.emit(name)

        if save_yaml:
            self._yaml.unset(name)

    def clear(self, *, save_yaml=False):
        """Clear all settings in the config.

        If save_yaml=True is given, also remove all customization from the YAML
        file.
        """
        old_values = self._values
        self._values = {}
        for name in old_values:
            self.changed.emit(name)

        if save_yaml:
            self._yaml.clear()

    def update_mutables(self, *, save_yaml=False):
        """Update mutable settings if they changed.

        Every time someone calls get_obj() on a mutable object, we save a
        reference to the original object and a copy.

        Here, we check all those saved copies for mutations, and if something
        mutated, we call set_obj again so we save the new value.
        """
        for name, (old_value, new_value) in self._mutables.items():
            if old_value != new_value:
                log.config.debug("{} was mutated, updating".format(name))
                self.set_obj(name, new_value, save_yaml=save_yaml)
        self._mutables = {}

    def dump_userconfig(self):
        """Get the part of the config which was changed by the user.

        Return:
            The changed config part as string.
        """
        lines = []
        for opt, value in self:
            str_value = opt.typ.to_str(value)
            lines.append('{} = {}'.format(opt.name, str_value))
        if not lines:
            lines = ['<Default configuration>']
        return '\n'.join(lines)


class ConfigContainer:

    """An object implementing config access via __getattr__.

    Attributes:
        _config: The Config object.
        _prefix: The __getattr__ chain leading up to this object.
        _configapi: If given, get values suitable for config.py and
                    add errors to the given ConfigAPI object.
    """

    def __init__(self, config, configapi=None, prefix=''):
        self._config = config
        self._prefix = prefix
        self._configapi = configapi

    def __repr__(self):
        return utils.get_repr(self, constructor=True, config=self._config,
                              configapi=self._configapi, prefix=self._prefix)

    @contextlib.contextmanager
    def _handle_error(self, action, name):
        try:
            yield
        except configexc.Error as e:
            if self._configapi is None:
                raise
            text = "While {} '{}'".format(action, name)
            self._configapi.errors.append(configexc.ConfigErrorDesc(text, e))

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
            return ConfigContainer(config=self._config,
                                   configapi=self._configapi,
                                   prefix=name)

        with self._handle_error('getting', name):
            if self._configapi is None:
                # access from Python code
                return self._config.get(name)
            else:
                # access from config.py
                return self._config.get_obj(name)

    def __setattr__(self, attr, value):
        """Set the given option in the config."""
        if attr.startswith('_'):
            return super().__setattr__(attr, value)

        name = self._join(attr)
        with self._handle_error('setting', name):
            self._config.set_obj(name, value)

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


@functools.lru_cache()
def _render_stylesheet(stylesheet):
    """Render the given stylesheet jinja template."""
    with jinja.environment.no_autoescape():
        template = jinja.environment.from_string(stylesheet)
    return template.render(conf=val)


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
        return _render_stylesheet(self._stylesheet)

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
