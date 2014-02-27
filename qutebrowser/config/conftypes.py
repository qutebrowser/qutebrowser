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

import qutebrowser.commands.utils as cmdutils


class BaseType:

    """A type used for a setting value.

    Attributes:
        valid_values: Possible values if they can be expressed as a fixed
                      string. Either a list of strings, or a list of (value,
                      desc) tuples.
                      # FIXME actually handle tuples and stuff when validating
        show_valid_values; Whether to show valid values in config or not.
        typestr: The name of the type to appear in the config.

    """

    typestr = None
    valid_values = None
    show_valid_values = True

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

class String(BaseType):

    """Base class for a string setting (case-insensitive)."""

    typestr = 'string'

    def transform(self, value):
        return value.lower()


class Bool(BaseType):

    """Base class for a boolean setting."""

    valid_values = ['true', 'false']
    show_valid_values = False
    typestr = 'bool'

    # Taken from configparser
    _BOOLEAN_STATES = {'1': True, 'yes': True, 'true': True, 'on': True,
                       '0': False, 'no': False, 'false': False, 'off': False}

    def transform(self, value):
        return self._BOOLEAN_STATES[value.lower()]

    def validate(self):
        return self.value.lower() in self._BOOLEAN_STATES


class Int(BaseType):

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


class List(BaseType):

    """Base class for a (string-)list setting."""

    typestr = 'string-list'

    def transform(self, value):
        return value.split(',')

    def validate(self):
        return True


class IntList(List):

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


class PercOrInt(BaseType):

    """Percentage or integer."""

    def validate(self):
        if self.value.endswith('%'):
            try:
                intval = int(self.value.rstrip('%'))
            except ValueError:
                return False
            else:
                return 0 <= intval <= 100
        else:
            try:
                intval = int(self.value)
            except ValueError:
                return False
            else:
                return intval > 0


class Command(BaseType):

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


class Color(BaseType):

    """Base class for a color value."""

    typestr = 'color'

    def validate(self):
        # FIXME validate colors
        return True


class Font(BaseType):

    """Base class for a font value."""

    typestr = 'font'

    def validate(self):
        # FIXME validate fonts
        return True


class SearchEngineName(BaseType):

    """A search engine name."""

    def validate(self):
        return True


class SearchEngineUrl(BaseType):

    """A search engine URL."""

    def validate(self):
        return "{}" in self.value


class KeyBindingName(BaseType):

    """The name (keys) of a keybinding."""

    def validate(self):
        # FIXME can we validate anything here?
        return True



class AutoSearch(BaseType):

    """Whether to start a search when something else than an URL is entered."""

    valid_values = [("naive", "Use simple/naive check."),
                    ("dns", "Use DNS requests (might be slow!)."),
                    ("false", "Never search automatically.")]

    def validate(self):
        if self.value.lower() in ["naive", "dns"]:
            return True
        else:
            return Bool.validate(self, self.value)

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

    valid_values = ["north", "south", "east", "west"]


class SelectOnRemove(String):

    """Which tab to select when the focused tab is removed."""

    valid_values = [("left", "Select the tab on the left."),
                    ("right", "Select the tab on the right."),
                    ("previous", "Select the previously selected tab.")]


class LastClose(String):

    """Behaviour when the last tab is closed."""

    valid_values = [("ignore", "Don't do anything."),
                    ("blank", "Load about:blank."),
                    ("quit", "Quit qutebrowser.")]


class KeyBinding(Command):

    """The command of a keybinding."""

    pass


