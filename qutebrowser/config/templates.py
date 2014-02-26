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

"""Templates for setting options."""

import logging

import qutebrowser.commands.utils as cmdutils


class SettingValue:

    """Base class for setting values.

    Intended to be subclassed by config value "types".

    Attributes:
        valid_values: Possible values if they can be expressed as a fixed
                      string. Either a list of strings, or a list of (value,
                      desc) tuples.
                      # FIXME actually handle tuples and stuff when validating

        default: Default value if the user has not overridden it, as a string.
        default_conf: Default value for the config, with interpolation.
        value: (property) The currently valid, most important, transformed
               value.
        rawvalue: The current value as a raw string.
        typestr: The name of the type to appear in the config.

    """

    valid_values = None
    default = None
    default_conf = None
    typestr = None
    rawvalue = None

    def __init__(self, rawval=None):
        """Constructor.

        Args:
            rawval: Raw value to set.

        """
        if rawval is not None:
            self.rawvalue = rawval

    def __str__(self):
        """Get raw string value."""
        return self.rawvalue if self.rawvalue is not None else ''

    @property
    def value(self):
        """Get the currently valid value."""
        if self.rawvalue is not None:
            val = self.rawvalue
        else:
            val = self.default
        return self.transform(val)

    def transform(self, value):
        """Transform the setting value.

        This method can assume the value is indeed a valid value.

        The default implementation returns the original value.

        Return:
            The transformed value.

        """
        return value

    def validate(self):
        """Validate value against possible values.

        The default implementation checks the value against self.valid_values
        if it was defined.

        Return:
            Ture if validation succeeded, False otherwise.

        Raise:
            NotImplementedError if self.valid_values is not defined and this
            method should be overridden.

        """
        if self.valid_values is not None:
            return self.value in self.valid_values
        else:
            raise NotImplementedError


class StringSettingValue(SettingValue):

    """Base class for a string setting (case-insensitive)."""

    typestr = 'string'

    def transform(self, value):
        return value.lower()


class BoolSettingValue(SettingValue):

    """Base class for a boolean setting."""

    valid_values = ['true', 'false']
    typestr = 'bool'

    # Taken from configparser
    _BOOLEAN_STATES = {'1': True, 'yes': True, 'true': True, 'on': True,
                       '0': False, 'no': False, 'false': False, 'off': False}

    def transform(self, value):
        return self._BOOLEAN_STATES[value.lower()]

    def validate(self):
        return self.value.lower() in self._BOOLEAN_STATES


class IntSettingValue(SettingValue):

    """Base class for an integer setting."""

    typestr = 'int'

    def transform(self, value):
        return int(value)

    def validate(self):
        try:
            int(self.value)
        except ValueError:
            return False
        else:
            return True


class ListSettingValue(SettingValue):

    """Base class for a (string-)list setting."""

    typestr = 'string-list'

    def transform(self, value):
        return value.split(',')

    def validate(self):
        return True


class IntListSettingValue(ListSettingValue):

    """Base class for an int-list setting."""

    typestr = 'int-list'

    def transform(self, value):
        vals = super().transform(value)
        return map(int, vals)

    def validate(self):
        try:
            self.transform(self.value)
        except ValueError:
            return False
        else:
            return True


class CommandSettingValue(SettingValue):

    """Base class for a command value with arguments."""

    typestr = 'command'

    valid_values = cmdutils.cmd_dict.items()

    def validate(self):
        # We need to import this here to avoid circular dependencies
        from qutebrowser.commands.parsers import (CommandParser,
                                                  NoSuchCommandError)
        cp = CommandParser()
        try:
            cp.parse(self.value)
        except NoSuchCommandError:
            return False
        else:
            return True


class ColorSettingValue(SettingValue):

    """Base class for a color value."""

    typestr = 'color'

    def validate(self):
        # FIXME validate colors
        return True


class FontSettingValue(SettingValue):

    """Base class for a font value."""

    typestr = 'font'

    def validate(self):
        # FIXME validate fonts
        return True


class ValueListSection:

    """This class represents a section with a list key-value settings.

    These are settings inside sections which don't have fixed keys, but instead
    have a dynamic list of "key = value" pairs, like keybindings or
    searchengines.

    They basically consist of two different SettingValues and have no defaults.

    Attributes:
        values: An OrderedDict with key as index and value as value.
        default: An OrderedDict with the default configuration as strings.
                 After __init__, the strings become key/value types.
        types: A tuple for (keytype, valuetype)

    """

    values = None
    default = None
    types = None

    def __init__(self):
        """Wrap types over default values. Take care when overriding this."""
        logging.debug("Default before wrapping: {}".format(self.default))
        self.default = {self.types[0](key): self.types[1](value)
                        for key, value in self.default.items()}

    def __str__(self):
        """Get the key = value pairs as a string."""
        return '\n'.join('{} = {}'.format(key.rawvalue, val.rawvalue)
                         for key, val in self.values)

    def __getitem__(self, key):
        """Get the value for key.

        Args:
            key: The key to get a value for, as a string.

        Return:
            The value, as value class.

        """
        try:
            return self.values[key]
        except KeyError:
            return self.defaults[key]

    def __iter__(self):
        """Iterate over all set values."""
        # FIXME using a custon iterator this could be done more efficiently
        valdict = self.default
        if self.values is not None:
            valdict.update(self.values)
        return valdict.__iter__()

    def items(self):
        """Get dict items."""
        valdict = self.default
        if self.values is not None:
            valdict.update(self.values)
        return valdict.items()
