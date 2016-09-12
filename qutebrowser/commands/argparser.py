# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
from qutebrowser.utils import utils, objreg, log


SUPPRESS = argparse.SUPPRESS


class ArgumentParserError(Exception):

    """Exception raised when the ArgumentParser signals an error."""


class ArgumentParserExit(Exception):

    """Exception raised when the argument parser exited.

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


def arg_name(name):
    """Get the name an argument should have based on its Python name."""
    return name.rstrip('_').replace('_', '-')


def _check_choices(param, value, choices):
    if value not in choices:
        expected_values = ', '.join(arg_name(val) for val in choices)
        raise cmdexc.ArgumentTypeError("{}: Invalid value {} - expected "
                                       "one of: {}".format(
                                           param.name, value, expected_values))


def type_conv(param, typ, value, *, str_choices=None):
    """Convert a value based on a type.

    Args:
        param: The argparse.Parameter we're checking
        types: The allowed type
        value: The value to convert
        str_choices: The allowed choices if the type ends up being a string

    Return:
        The converted value
    """
    if isinstance(typ, str):
        raise TypeError("{}: Legacy string type!".format(param.name))

    if value is param.default:
        return value

    assert isinstance(value, str), repr(value)

    if utils.is_enum(typ):
        _check_choices(param, value, [arg_name(e.name) for e in typ])
        return typ[value.replace('-', '_')]
    elif typ is str:
        if str_choices is not None:
            _check_choices(param, value, str_choices)
        return value
    elif callable(typ):
        # int, float, etc.
        try:
            return typ(value)
        except (TypeError, ValueError):
            msg = '{}: Invalid {} value {}'.format(
                param.name, typ.__name__, value)
            raise cmdexc.ArgumentTypeError(msg)
    else:
        raise ValueError("{}: Unknown type {!r}!".format(param.name, typ))


def multitype_conv(param, types, value, *, str_choices=None):
    """Convert a value based on a choice of types.

    Args:
        param: The inspect.Parameter we're checking
        types: The allowed types ("overloads")
        value: The value to convert
        str_choices: The allowed choices if the type ends up being a string

    Return:
        The converted value
    """
    types = list(set(types))
    if str in types:
        # Make sure str is always the last type in the list, so e.g. '23' gets
        # returned as 23 if we have typing.Union[str, int]
        types.remove(str)
        types.append(str)

    for typ in types:
        log.commands.debug("Trying to parse {!r} as {}".format(value, typ))
        try:
            return type_conv(param, typ, value, str_choices=str_choices)
        except cmdexc.ArgumentTypeError as e:
            log.commands.debug("Got {} for {}".format(e, typ))
    raise cmdexc.ArgumentTypeError('{}: Invalid value {}'.format(
        param.name, value))
