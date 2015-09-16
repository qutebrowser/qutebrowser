# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""argparse.ArgumentParser subclass to parse qutebrowser commands."""


import argparse

from PyQt5.QtCore import QUrl

from qutebrowser.commands import cmdexc
from qutebrowser.utils import utils, objreg


SUPPRESS = argparse.SUPPRESS


class ArgumentParserError(Exception):

    """Exception raised when the ArgumentParser signals an error."""


class ArgumentParserExit(Exception):

    """Exception raised when the argument parser exitted.

    Attributes:
        status: The exit status.
    """

    def __init__(self, status, msg):
        self.status = status
        super().__init__(msg)


class HelpAction(argparse.Action):

    """Argparse action to open the help page in the browser.

    This is horrible encapsulation, but I can't think of a good way to do this
    better...
    """

    def __call__(self, parser, _namespace, _values, _option_string=None):
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window='last-focused')
        tabbed_browser.tabopen(
            QUrl('qute://help/commands.html#{}'.format(parser.name)))
        parser.exit()


class ArgumentParser(argparse.ArgumentParser):

    """Subclass ArgumentParser to be more suitable for runtime parsing.

    Attributes:
        name: The command name.
    """

    def __init__(self, name, *args, **kwargs):
        self.name = name
        super().__init__(*args, add_help=False, prog=name, **kwargs)

    def exit(self, status=0, msg=None):
        raise ArgumentParserExit(status, msg)

    def error(self, msg):
        raise ArgumentParserError(msg.capitalize())


def enum_getter(enum):
    """Function factory to get an enum getter."""
    def _get_enum_item(key):
        """Helper function to get an enum item.

        Passes through existing items unmodified.
        """
        if isinstance(key, enum):
            return key
        try:
            return enum[key.replace('-', '_')]
        except KeyError:
            raise cmdexc.ArgumentTypeError("Invalid value {}.".format(key))

    return _get_enum_item


def multitype_conv(types):
    """Function factory to get a type converter for a choice of types."""
    def _convert(value):
        """Convert a value according to an iterable of possible arg types."""
        for typ in set(types):
            if isinstance(typ, str):
                if value == typ:
                    return value
            elif utils.is_enum(typ):
                return enum_getter(typ)(value)
            elif callable(typ):
                # int, float, etc.
                if isinstance(value, typ):
                    return value
                try:
                    return typ(value)
                except (TypeError, ValueError):
                    pass
            else:
                raise ValueError("Unknown type {!r}!".format(typ))
        raise cmdexc.ArgumentTypeError('Invalid value {}.'.format(value))

    return _convert
