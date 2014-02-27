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

from collections import OrderedDict


class SettingValue:

    """Base class for setting values.

    Intended to be subclassed by config value "types".

    Attributes:
        typ: A BaseType subclass.
        default: Default value if the user has not overridden it, as a string.
        default_conf: Default value for the config, with interpolation.
        value: (property) The currently valid, most important, transformed
               value.
        rawvalue: The current value as a raw string.

    """

    def __init__(self, typ, default, default_conf=None):
        """Constructor.

        Args:
            typ: The BaseType to use.
            default: Raw value to set.
            default_conf: Raw value to set, for the config.

        """
        self.typ = typ()
        self.rawvalue = None
        self.default = default
        self.default_conf = default_conf

    def __str__(self):
        """Get raw string value."""
        if self.rawvalue is not None:
            val = self.rawvalue
        else:
            val = (self.default_conf if self.default_conf is not None
                   else self.default)
        return val

    @property
    def value(self):
        """Get the currently valid value."""
        if self.rawvalue is not None:
            val = self.rawvalue
        else:
            val = self.default
        return self.typ.transform(val)


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
        self.values = OrderedDict()
        keytype = self.types[0]()
        valtype = self.types[1]()
        self.default = {keytype.transform(key): valtype.transform(value)
                        for key, value in self.default.items()}

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
            return self.default[key]

    def __iter__(self):
        """Iterate over all set values."""
        # FIXME using a custon iterator this could be done more efficiently
        valdict = self.default
        if self.values is not None:
            valdict.update(self.values)
        return valdict.__iter__()

    def __bool__(self):
        """Get boolean state of section."""
        # FIXME we really should cache valdict
        valdict = self.default
        if self.values is not None:
            valdict.update(self.values)
        return bool(valdict)

    def items(self):
        """Get dict items."""
        valdict = self.default
        if self.values is not None:
            valdict.update(self.values)
        return valdict.items()
