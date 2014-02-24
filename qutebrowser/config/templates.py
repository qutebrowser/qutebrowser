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

import qutebrowser.commands.utils as cmdutils

class SettingValue:

    """Base class for settings. The docstring is used as a description."""

    # Possible values, if they are fixed.
    # Either a list of strings, or a list of (value, desc) tuples.
    values = None

    # Default value if user has not overriden it, as a string.
    default = None

    def transform(self, value):
        """Transform the setting value.

        This method can assume the value is indeed a valid value.

        The default implementation returns the original value.

        Args:
            value: The value to transform.

        Return:
            The transformed value.

        """
        return value

    def validate(self, value):
        """Validate value against possible values.

        The default implementation checks the value against self.values if it
        was defined.

        Args:
            value: The value to validate.

        Return:
            Ture if validation succeeded, False otherwise.

        Raise:
            NotImplementedError if self.values is not defined and this method
            should be overridden.

        """
        if self.values is not None:
            return value in self.values
        else:
            raise NotImplementedError

class BoolSettingValue(SettingValue):

    """Base class for a boolean setting."""
    values = ['true', 'false']

    # Taken from configparser
    _BOOLEAN_STATES = {'1': True, 'yes': True, 'true': True, 'on': True,
                       '0': False, 'no': False, 'false': False, 'off': False}

    def transform(self, value):
        return self._BOOLEAN_STATES[value.lower()]

    def validate(self, value):
        return value.lower() in self._BOOLEAN_STATES


class IntSettingValue(SettingValue):

    """Base class for an integer setting."""

    def transform(self, value):
        return int(value)

    def validate(self, value):
        try:
            int(value)
        except ValueError:
            return False
        else:
            return True


class ListSettingValue(SettingValue):

    """Base class for a (string-)list setting."""

    def transform(self, value):
        return value.split(',')

    def validate(self, value):
        return True


class IntListSettingValue(ListSettingValue):

    """Base class for an int-list setting."""

    def transform(self, value):
        vals = super().transform(value)
        return map(int, vals)

    def validate(self, value)
        try:
            self.transform(value)
        except ValueError:
            return False
        else:
            return True


class CommandSettingValue(SettingValue):

    """Base class for a command value with arguments."""

    values = cmdutils.cmd_dict.values()

    def validate(self, value):
        cp = cmdutils.CommandParser()
        try:
            cp.parse(value)
        except cmdutils.NoSuchCommandError:
            return False
        else:
            return True


class ColorSettingValue(SettingValue):

    """Base class for a color value."""

    def validate(self, value):
        # FIXME validate colors
        return True


class FontSettingValue(SettingValue):

    """Base class for a font value."""

    def validate(self, value):
        # FIXME validate fonts
        return True
