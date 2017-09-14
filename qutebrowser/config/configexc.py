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

"""Exceptions related to config parsing."""


import traceback


class Error(Exception):

    """Base exception for config-related errors."""

    pass


class BackendError(Error):

    """Raised when this setting is unavailable with the current backend."""

    def __init__(self, backend):
        super().__init__("This setting is not available with the {} "
                         "backend!".format(backend.name))


class ValidationError(Error):

    """Raised when a value for a config type was invalid.

    Attributes:
        value: Config value that triggered the error.
        msg: Additional error message.
    """

    def __init__(self, value, msg):
        super().__init__("Invalid value '{}' - {}".format(value, msg))
        self.option = None


class KeybindingError(Error):

    """Raised for issues with keybindings."""


class DuplicateKeyError(KeybindingError):

    """Raised when there was a duplicate key."""

    def __init__(self, key):
        super().__init__("Duplicate key {}".format(key))


class NoOptionError(Error):

    """Raised when an option was not found."""

    def __init__(self, option):
        super().__init__("No option {!r}".format(option))
        self.option = option


class ConfigFileError(Error):

    """Raised when there was an error while loading a config file."""

    def __init__(self, basename, msg):
        super().__init__("Failed to load {}: {}".format(basename, msg))


class ConfigFileUnhandledException(ConfigFileError):

    """Raised when there was an unhandled exception while loading config.py.

    Needs to be raised from an exception handler.
    """

    def __init__(self, basename):
        super().__init__(basename, "Unhandled exception\n\n{}".format(
            traceback.format_exc()))


class ConfigErrorDesc:

    """A description of an error happening while reading the config.

    Attributes:
        _action: What action has been taken, e.g 'set'
        _name: The option which was set, or the key which was bound.
        _exception: The exception which happened.
    """

    def __init__(self, action, name, exception):
        self._action = action
        self._exception = exception
        self._name = name

    def __str__(self):
        return "While {} {}: {}".format(
            self._action, self._name, self._exception)


class ConfigFileErrors(ConfigFileError):

    """Raised when multiple errors occurred inside the config."""

    def __init__(self, basename, errors):
        super().__init__(basename, "\n\n".join(str(err) for err in errors))
