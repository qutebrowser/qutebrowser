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

"""Setting options used for qutebrowser."""


class ValidationError(ValueError):

    """Exception raised when a value for a config type was invalid."""

    pass


class ValidValues:

    """Container for valid values for a given type.

    Attributes:
        values: A list with the allowed untransformed values.
        descriptions: A dict with value/desc mappings.
        show: Whether to show the values in the config or not.

    """

    def __init__(self, *vals, show=True):
        self.descriptions = {}
        self.values = []
        self.show = show
        for v in vals:
            if isinstance(v, str):
                # Value without description
                self.values.append(v)
            else:
                # (value, description) tuple
                self.values.append(v[0])
                self.descriptions[v[0]] = v[1]

    def __contains__(self, val):
        return val in self.values

    def __iter__(self):
        return self.values.__iter__()


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
        self.rawvalue = val


class BaseType:

    """A type used for a setting value.

    Attributes:
        valid_values: Possible values if they can be expressed as a fixed
                      string. ValidValues instance.
        typestr: The name of the type to appear in the config.

    """

    typestr = None
    valid_values = None

    def transform(self, value):
        """Transform the setting value.

        This method can assume the value is indeed a valid value.

        The default implementation returns the original value.

        Args:
            value: The original string value.

        Return:
            The transformed value.

        """
        return value

    def validate(self, value):
        """Validate value against possible values.

        The default implementation checks the value against self.valid_values
        if it was defined.

        Args:
            value: The value to validate.

        Raise:
            ValidationError if the value was invalid.
            NotImplementedError if self.valid_values is not defined and this
            method should be overridden.

        """
        if self.valid_values is not None:
            if value not in self.valid_values:
                raise ValidationError
            else:
                return
        else:
            raise NotImplementedError


class String(BaseType):

    """Base class for a string setting (case-insensitive)."""

    typestr = 'string'

    def transform(self, value):
        return value.lower()


class Bool(BaseType):

    """Base class for a boolean setting."""

    valid_values = ValidValues('true', 'false', show=False)
    typestr = 'bool'

    # Taken from configparser
    _BOOLEAN_STATES = {'1': True, 'yes': True, 'true': True, 'on': True,
                       '0': False, 'no': False, 'false': False, 'off': False}

    def transform(self, value):
        return self._BOOLEAN_STATES[value.lower()]

    def validate(self, value):
        if value.lower() not in self._BOOLEAN_STATES:
            raise ValidationError


class Int(BaseType):

    """Base class for an integer setting."""

    typestr = 'int'

    def transform(self, value):
        return int(value)

    def validate(self, value):
        try:
            int(value)
        except ValueError:
            raise ValidationError


class List(BaseType):

    """Base class for a (string-)list setting."""

    typestr = 'string-list'

    def transform(self, value):
        return value.split(',')

    def validate(self, value):
        pass


class IntList(List):

    """Base class for an int-list setting."""

    typestr = 'int-list'

    def transform(self, value):
        vals = super().transform(value)
        return map(int, vals)

    def validate(self, value):
        try:
            self.transform(value)
        except ValueError:
            raise ValidationError


class PercOrInt(BaseType):

    """Percentage or integer."""

    def validate(self, value):
        if value.endswith('%'):
            try:
                intval = int(value.rstrip('%'))
            except ValueError:
                raise ValidationError
            else:
                if not 0 <= intval <= 100:
                    raise ValidationError
        else:
            try:
                intval = int(value)
            except ValueError:
                raise ValidationError
            else:
                if intval < 0:
                    raise ValidationError


class Command(BaseType):

    """Base class for a command value with arguments."""

    # FIXME we need to use this without having problems with circular imports.

    typestr = 'command'

    #valid_values = ValidValues(*cmdutils.cmd_dict.items())

    def validate(self, value):
        #from qutebrowser.commands.parsers import (CommandParser,
        #                                          NoSuchCommandError)
        #cp = CommandParser()
        #try:
        #    cp.parse(value)
        #except NoSuchCommandError:
        #    raise ValidationError
        pass


class Color(BaseType):

    """Base class for a color value."""

    typestr = 'color'

    def validate(self, value):
        # FIXME validate colors
        pass


class Font(BaseType):

    """Base class for a font value."""

    typestr = 'font'

    def validate(self, value):
        # FIXME validate fonts
        pass


class SearchEngineName(BaseType):

    """A search engine name."""

    def validate(self, value):
        pass


class SearchEngineUrl(BaseType):

    """A search engine URL."""

    def validate(self, value):
        return "{}" in value


class KeyBindingName(BaseType):

    """The name (keys) of a keybinding."""

    def validate(self, value):
        # FIXME can we validate anything here?
        pass


class AutoSearch(BaseType):

    """Whether to start a search when something else than an URL is entered."""

    valid_values = ValidValues(("naive", "Use simple/naive check."),
                               ("dns", "Use DNS requests (might be slow!)."),
                               ("false", "Never search automatically."))

    def validate(self, value):
        if value.lower() in ["naive", "dns"]:
            pass
        else:
            Bool.validate(self, value)

    def transform(self, value):
        if value.lower() in ["naive", "dns"]:
            return value.lower()
        elif super().transform(value):
            # boolean true is an alias for naive matching
            return "naive"
        else:
            return False


class Position(String):

    """The position of the tab bar."""

    valid_values = ValidValues("north", "south", "east", "west")


class SelectOnRemove(String):

    """Which tab to select when the focused tab is removed."""

    valid_values = ValidValues(
        ("left", "Select the tab on the left."),
        ("right", "Select the tab on the right."),
        ("previous", "Select the previously selected tab."))


class LastClose(String):

    """Behaviour when the last tab is closed."""

    valid_values = ValidValues(("ignore", "Don't do anything."),
                               ("blank", "Load about:blank."),
                               ("quit", "Quit qutebrowser."))


class KeyBinding(Command):

    """The command of a keybinding."""

    pass
