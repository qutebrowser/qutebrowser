# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from qutebrowser.config import configdata, configexc, configutils
from qutebrowser.utils import utils, log, jinja
from qutebrowser.misc import objects
from qutebrowser.keyinput import keyutils

# An easy way to access the config from other code via config.val.foo
val = None
instance = None
key_instance = None

# Keeping track of all change filters to validate them later.
change_filters = []

# Sentinel
UNSET = object()


class change_filter:  # noqa: N801,N806 pylint: disable=invalid-name

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
                """Call the underlying function."""
                if self._check_match(option):
                    return func()
                return None
        else:
            @functools.wraps(func)
            def wrapper(wrapper_self, option=None):
                """Call the underlying function."""
                if self._check_match(option):
                    return func(wrapper_self)
                return None

        return wrapper


class KeyConfig:

    """Utilities related to keybindings.

    Note that the actual values are saved in the config itself, not here.

    Attributes:
        _config: The Config object to be used.
    """

    def __init__(self, config):
        self._config = config

    def _validate(self, key, mode):
        """Validate the given key and mode."""
        # Catch old usage of this code
        assert isinstance(key, keyutils.KeySequence), key
        if mode not in configdata.DATA['bindings.default'].default:
            raise configexc.KeybindingError("Invalid mode {}!".format(mode))

    def get_bindings_for(self, mode):
        """Get the combined bindings for the given mode."""
        bindings = dict(val.bindings.default[mode])
        for key, binding in val.bindings.commands[mode].items():
            if not binding:
                bindings.pop(key, None)
            else:
                bindings[key] = binding
        return bindings

    def get_reverse_bindings_for(self, mode):
        """Get a dict of commands to a list of bindings for the mode."""
        cmd_to_keys = {}
        bindings = self.get_bindings_for(mode)
        for seq, full_cmd in sorted(bindings.items()):
            for cmd in full_cmd.split(';;'):
                cmd = cmd.strip()
                cmd_to_keys.setdefault(cmd, [])
                # Put bindings involving modifiers last
                if any(info.modifiers for info in seq):
                    cmd_to_keys[cmd].append(str(seq))
                else:
                    cmd_to_keys[cmd].insert(0, str(seq))
        return cmd_to_keys

    def get_command(self, key, mode, default=False):
        """Get the command for a given key (or None)."""
        self._validate(key, mode)
        if default:
            bindings = dict(val.bindings.default[mode])
        else:
            bindings = self.get_bindings_for(mode)
        return bindings.get(key, None)

    def bind(self, key, command, *, mode, save_yaml=False):
        """Add a new binding from key to command."""
        if command is not None and not command.strip():
            raise configexc.KeybindingError(
                "Can't add binding '{}' with empty command in {} "
                'mode'.format(key, mode))

        self._validate(key, mode)
        log.keyboard.vdebug("Adding binding {} -> {} in mode {}.".format(
            key, command, mode))

        bindings = self._config.get_mutable_obj('bindings.commands')
        if mode not in bindings:
            bindings[mode] = {}
        bindings[mode][str(key)] = command
        self._config.update_mutables(save_yaml=save_yaml)

    def bind_default(self, key, *, mode='normal', save_yaml=False):
        """Restore a default keybinding."""
        self._validate(key, mode)

        bindings_commands = self._config.get_mutable_obj('bindings.commands')
        try:
            del bindings_commands[mode][str(key)]
        except KeyError:
            raise configexc.KeybindingError(
                "Can't find binding '{}' in {} mode".format(key, mode))
        self._config.update_mutables(save_yaml=save_yaml)

    def unbind(self, key, *, mode='normal', save_yaml=False):
        """Unbind the given key in the given mode."""
        self._validate(key, mode)

        bindings_commands = self._config.get_mutable_obj('bindings.commands')

        if val.bindings.commands[mode].get(key, None) is not None:
            # In custom bindings -> remove it
            del bindings_commands[mode][str(key)]
        elif key in val.bindings.default[mode]:
            # In default bindings -> shadow it with None
            if mode not in bindings_commands:
                bindings_commands[mode] = {}
            bindings_commands[mode][str(key)] = None
        else:
            raise configexc.KeybindingError(
                "Can't find binding '{}' in {} mode".format(key, mode))

        self._config.update_mutables(save_yaml=save_yaml)


class Config(QObject):

    """Main config object.

    Class attributes:
        MUTABLE_TYPES: Types returned from the config which could potentially
        be mutated.

    Attributes:
        _values: A dict mapping setting names to configutils.Values objects.
        _mutables: A dictionary of mutable objects to be checked for changes.
        _yaml: A YamlConfig object or None.

    Signals:
        changed: Emitted with the option name when an option changed.
    """

    MUTABLE_TYPES = (dict, list)
    changed = pyqtSignal(str)

    def __init__(self, yaml_config, parent=None):
        super().__init__(parent)
        self.changed.connect(_render_stylesheet.cache_clear)
        self._mutables = {}
        self._yaml = yaml_config
        self._init_values()

    def _init_values(self):
        """Populate the self._values dict."""
        self._values = {}
        for name, opt in configdata.DATA.items():
            self._values[name] = configutils.Values(opt)

    def __iter__(self):
        """Iterate over configutils.Values items."""
        yield from self._values.values()

    def init_save_manager(self, save_manager):
        """Make sure the config gets saved properly.

        We do this outside of __init__ because the config gets created before
        the save_manager exists.
        """
        self._yaml.init_save_manager(save_manager)

    def _set_value(self, opt, value, pattern=None):
        """Set the given option to the given value."""
        if not isinstance(objects.backend, objects.NoBackend):
            if objects.backend not in opt.backends:
                raise configexc.BackendError(opt.name, objects.backend)

        opt.typ.to_py(value)  # for validation

        self._values[opt.name].add(opt.typ.from_obj(value), pattern)

        self.changed.emit(opt.name)
        log.config.debug("Config option changed: {} = {}".format(
            opt.name, value))

    def _check_yaml(self, opt, save_yaml):
        """Make sure the given option may be set in autoconfig.yml."""
        if save_yaml and opt.no_autoconfig:
            raise configexc.NoAutoconfigError(opt.name)

    def read_yaml(self):
        """Read the YAML settings from self._yaml."""
        self._yaml.load()
        for values in self._yaml:
            for scoped in values:
                self._set_value(values.opt, scoped.value,
                                pattern=scoped.pattern)

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

    def get(self, name, url=None):
        """Get the given setting converted for Python code."""
        opt = self.get_opt(name)
        obj = self.get_obj(name, url=url)
        return opt.typ.to_py(obj)

    def _maybe_copy(self, value):
        """Copy the value if it could potentially be mutated."""
        if isinstance(value, self.MUTABLE_TYPES):
            # For mutable objects, create a copy so we don't accidentally
            # mutate the config's internal value.
            return copy.deepcopy(value)
        else:
            # Shouldn't be mutable (and thus hashable)
            assert value.__hash__ is not None, value
            return value

    def get_obj(self, name, *, url=None):
        """Get the given setting as object (for YAML/config.py).

        Note that the returned values are not watched for mutation.
        If a URL is given, return the value which should be used for that URL.
        """
        self.get_opt(name)  # To make sure it exists
        value = self._values[name].get_for_url(url)
        return self._maybe_copy(value)

    def get_obj_for_pattern(self, name, *, pattern):
        """Get the given setting as object (for YAML/config.py).

        This gets the overridden value for a given pattern, or
        configutils.UNSET if no such override exists.
        """
        self.get_opt(name)  # To make sure it exists
        value = self._values[name].get_for_pattern(pattern, fallback=False)
        return self._maybe_copy(value)

    def get_mutable_obj(self, name, *, pattern=None):
        """Get an object which can be mutated, e.g. in a config.py.

        If a pattern is given, return the value for that pattern.
        Note that it's impossible to get a mutable object for an URL as we
        wouldn't know what pattern to apply.
        """
        self.get_opt(name)  # To make sure it exists

        # If we allow mutation, there is a chance that prior mutations already
        # entered the mutable dictionary and thus further copies are unneeded
        # until update_mutables() is called
        if name in self._mutables:
            _copy, obj = self._mutables[name]
            return obj

        value = self._values[name].get_for_pattern(pattern)
        copy_value = self._maybe_copy(value)

        # Watch the returned object for changes if it's mutable.
        if isinstance(copy_value, self.MUTABLE_TYPES):
            self._mutables[name] = (value, copy_value)  # old, new

        return copy_value

    def get_str(self, name, *, pattern=None):
        """Get the given setting as string.

        If a pattern is given, get the setting for the given pattern or
        configutils.UNSET.
        """
        opt = self.get_opt(name)
        values = self._values[name]
        value = values.get_for_pattern(pattern)
        return opt.typ.to_str(value)

    def set_obj(self, name, value, *, pattern=None, save_yaml=False):
        """Set the given setting from a YAML/config.py object.

        If save_yaml=True is given, store the new value to YAML.
        """
        opt = self.get_opt(name)
        self._check_yaml(opt, save_yaml)
        self._set_value(opt, value, pattern=pattern)
        if save_yaml:
            self._yaml.set_obj(name, value, pattern=pattern)

    def set_str(self, name, value, *, pattern=None, save_yaml=False):
        """Set the given setting from a string.

        If save_yaml=True is given, store the new value to YAML.
        """
        opt = self.get_opt(name)
        self._check_yaml(opt, save_yaml)
        converted = opt.typ.from_str(value)
        log.config.debug("Setting {} (type {}) to {!r} (converted from {!r})"
                         .format(name, opt.typ.__class__.__name__, converted,
                                 value))
        self._set_value(opt, converted, pattern=pattern)
        if save_yaml:
            self._yaml.set_obj(name, converted, pattern=pattern)

    def unset(self, name, *, save_yaml=False, pattern=None):
        """Set the given setting back to its default."""
        opt = self.get_opt(name)
        self._check_yaml(opt, save_yaml)
        changed = self._values[name].remove(pattern)
        if changed:
            self.changed.emit(name)

        if save_yaml:
            self._yaml.unset(name, pattern=pattern)

    def clear(self, *, save_yaml=False):
        """Clear all settings in the config.

        If save_yaml=True is given, also remove all customization from the YAML
        file.
        """
        for name, values in self._values.items():
            if values:
                values.clear()
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
        blocks = []
        for values in sorted(self, key=lambda v: v.opt.name):
            if values:
                blocks.append(str(values))

        if not blocks:
            return '<Default configuration>'

        return '\n'.join(blocks)


class ConfigContainer:

    """An object implementing config access via __getattr__.

    Attributes:
        _config: The Config object.
        _prefix: The __getattr__ chain leading up to this object.
        _configapi: If given, get values suitable for config.py and
                    add errors to the given ConfigAPI object.
        _pattern: The URL pattern to be used.
    """

    def __init__(self, config, configapi=None, prefix='', pattern=None):
        self._config = config
        self._prefix = prefix
        self._configapi = configapi
        self._pattern = pattern
        if configapi is None and pattern is not None:
            raise TypeError("Can't use pattern without configapi!")

    def __repr__(self):
        return utils.get_repr(self, constructor=True, config=self._config,
                              configapi=self._configapi, prefix=self._prefix,
                              pattern=self._pattern)

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
                                   prefix=name, pattern=self._pattern)

        with self._handle_error('getting', name):
            if self._configapi is None:
                # access from Python code
                return self._config.get(name)
            else:
                # access from config.py
                return self._config.get_mutable_obj(
                    name, pattern=self._pattern)

    def __setattr__(self, attr, value):
        """Set the given option in the config."""
        if attr.startswith('_'):
            super().__setattr__(attr, value)
            return

        name = self._join(attr)
        with self._handle_error('setting', name):
            self._config.set_obj(name, value, pattern=self._pattern)

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
    observer = StyleSheetObserver(obj, stylesheet, update)
    observer.register()


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

    def __init__(self, obj, stylesheet, update):
        super().__init__()
        self._obj = obj
        self._update = update

        # We only need to hang around if we are asked to update.
        if self._update:
            self.setParent(self._obj)
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

    def register(self):
        """Do a first update and listen for more.

        Args:
            update: if False, don't listen for future updates.
        """
        qss = self._get_stylesheet()
        log.config.vdebug("stylesheet for {}: {}".format(
            self._obj.__class__.__name__, qss))
        self._obj.setStyleSheet(qss)
        if self._update:
            instance.changed.connect(self._update_stylesheet)
