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

"""New qutebrowser configuration code."""

import functools

from PyQt5.QtCore import pyqtSignal, QObject

from qutebrowser.config import configdata, configexc
from qutebrowser.utils import utils, objreg

# An easy way to access the config from other code via config.val.foo
val = None
instance = None

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


class NewConfigManager(QObject):

    changed = pyqtSignal(str, str)  # FIXME:conf stub...

    def __init__(self, parent=None):
        super().__init__(parent)
        self.options = {}

    def read_defaults(self):
        for name, option in configdata.DATA.items():
            self.options[name] = option

    def get(self, option):
        try:
            opt = self.options[option]
        except KeyError:
            raise configexc.NoOptionError(option)
        return opt.typ.to_py(opt.default)

    def get_str(self, option):
        try:
            opt = self.options[option]
        except KeyError:
            raise configexc.NoOptionError(option)
        return opt.typ.to_str(opt.default)

    def set(self, option, value):
        raise configexc.Error("Setting doesn't work yet!")


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


def init(parent):
    new_config = NewConfigManager(parent)
    new_config.read_defaults()
    objreg.register('config', new_config)

    global val, instance
    val = ConfigContainer(new_config)
    instance = new_config

    for cf in _change_filters:
        cf.validate()
