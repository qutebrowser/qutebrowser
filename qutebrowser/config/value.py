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

"""A single value (with multiple layers possibly) in the config."""

from collections import namedtuple

ValueLayers = namedtuple('ValueLayers', 'temp, conf, default')


class SettingValue:

    """Base class for setting values.

    Intended to be subclassed by config value "types".

    Attributes:
        typ: A BaseType subclass.
        value: (readonly property) The currently valid, most important value.
        _values: A namedtuple with the values on different layers, with the
                 most significant layer first.
    """

    def __init__(self, typ, default=None):
        """Constructor.

        Args:
            typ: The BaseType to use.
            default: Raw value to set.
        """
        self.typ = typ()
        self._values = ValueLayers(None, None, None)
        self._values.default = default

    def __str__(self):
        """Get raw string value."""
        return self.value

    @property
    def value(self):
        """Get the currently valid value."""
        for val in self._values:
            if val is not None:
                return val
        else:
            raise ValueError("No valid config value found!")

    @property
    def values(self):
        """Readonly property for _values."""
        return self._values

    def transformed(self):
        """Get the transformed value."""
        v = self.value
        return self.typ.transform(v)

    def setv(self, layer, value):
        """Set the value on a layer.

        Arguments:
            layer: The layer to set the value on, an element name of the
                   ValueLayers namedtuple.
            value: The value to set.
        """
        self.typ.validate(value)
        setattr(self._values, layer, value)
