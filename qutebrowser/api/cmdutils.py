# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Utilities for command handlers."""

import inspect
import typing
import enum

from qutebrowser.utils import qtutils
from qutebrowser.commands import command, cmdexc
# pylint: disable=unused-import
from qutebrowser.utils.usertypes import CommandValue as Value


class CommandError(cmdexc.Error):

    """Raised when a command encounters an error while running.

    If your command handler encounters an error and cannot continue, raise this
    exception with an appropriate error message:

        raise cmdexc.CommandError("Message")

    The message will then be shown in the qutebrowser status bar.

    Note that you should only raise this exception while a command handler is
    run. Raising it at another point causes qutebrowser to crash due to an
    unhandled exception.
    """


def check_overflow(arg: int, ctype: str) -> None:
    """Check if the given argument is in bounds for the given type.

    Args:
        arg: The argument to check.
        ctype: The C++/Qt type to check as a string ('int'/'int64').
    """
    try:
        qtutils.check_overflow(arg, ctype)
    except OverflowError:
        raise CommandError("Numeric argument is too large for internal {} "
                           "representation.".format(ctype))


def check_exclusive(flags: typing.Iterable[bool],
                    names: typing.Iterable[str]) -> None:
    """Check if only one flag is set with exclusive flags.

    Raise a CommandError if not.

    Args:
        flags: The flag values to check.
        names: A list of names (corresponding to the flags argument).
    """
    if sum(1 for e in flags if e) > 1:
        argstr = '/'.join('-' + e for e in names)
        raise CommandError("Only one of {} can be given!".format(argstr))


class register:  # noqa: N801,N806 pylint: disable=invalid-name

    """Decorator to register a new command handler.

    Attributes:
        _instance: The object from the object registry to be used as "self".
        _name: The name (as string) or names (as list) of the command.
        _kwargs: The arguments to pass to Command.
    """

    def __init__(self, *,
                 instance: str = None,
                 name: str = None,
                 **kwargs: typing.Any) -> None:
        """Save decorator arguments.

        Gets called on parse-time with the decorator arguments.

        Args:
            See class attributes.
        """
        self._instance = instance
        self._name = name
        self._kwargs = kwargs

    def __call__(self, func: typing.Callable) -> typing.Callable:
        """Register the command before running the function.

        Gets called when a function should be decorated.

        Doesn't actually decorate anything, but creates a Command object and
        registers it in the global commands dict.

        Args:
            func: The function to be decorated.

        Return:
            The original function (unmodified).
        """
        if self._name is None:
            name = func.__name__.lower().replace('_', '-')
        else:
            assert isinstance(self._name, str), self._name
            name = self._name

        cmd = command.Command(name=name, instance=self._instance,
                              handler=func, **self._kwargs)
        cmd.register()
        return func


class argument:  # noqa: N801,N806 pylint: disable=invalid-name

    """Decorator to customize an argument for @cmdutils.register.

    Attributes:
        _argname: The name of the argument to handle.
        _kwargs: Keyword arguments, valid ArgInfo members
    """

    def __init__(self, argname: str, **kwargs: typing.Any) -> None:
        self._argname = argname
        self._kwargs = kwargs

    def __call__(self, func: typing.Callable) -> typing.Callable:
        funcname = func.__name__

        if self._argname not in inspect.signature(func).parameters:
            raise ValueError("{} has no argument {}!".format(funcname,
                                                             self._argname))
        if not hasattr(func, 'qute_args'):
            func.qute_args = {}  # type: ignore
        elif func.qute_args is None:  # type: ignore
            raise ValueError("@cmdutils.argument got called above (after) "
                             "@cmdutils.register for {}!".format(funcname))

        arginfo = command.ArgInfo(**self._kwargs)
        func.qute_args[self._argname] = arginfo  # type: ignore

        return func
