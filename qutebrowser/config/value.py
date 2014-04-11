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


class SettingValue:

    """Base class for setting values.

    Intended to be subclassed by config value "types".

    Attributes:
        typ: A BaseType subclass.
        default: Default value if the user has not overridden it, as a string.
        value: (property) The currently valid, most important value.
        rawvalue: The current value as a raw string.
    """

    def __init__(self, typ, default=None):
        """Constructor.

        Args:
            typ: The BaseType to use.
            default: Raw value to set.
        """
        self.typ = typ()
        self.rawvalue = None
        self.default = default

    def __str__(self):
        """Get raw string value."""
        return self.value

    def transformed(self):
        """Get the transformed value."""
        v = self.value
        return self.typ.transform(v)

    @property
    def value(self):
        """Get the currently valid value."""
        return self.rawvalue if self.rawvalue is not None else self.default

    @value.setter
    def value(self, val):
        """Set the currently valid value."""
        self.typ.validate(val)
        self.rawvalue = val
