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

"""Contains various command utils and a global command dict.

Module attributes:
    cmd_dict: A mapping from command-strings to command objects.
    aliases: A list of all aliases, needed for doc generation.
"""

import inspect

from qutebrowser.utils import qtutils, log
from qutebrowser.commands import command, cmdexc

cmd_dict = {}
aliases = []


def check_overflow(arg, ctype):
    """Check if the given argument is in bounds for the given type.

    Args:
        arg: The argument to check
        ctype: The C/Qt type to check as a string.
    """
    try:
        qtutils.check_overflow(arg, ctype)
    except OverflowError:
        raise cmdexc.CommandError(
            "Numeric argument is too large for internal {} "
            "representation.".format(ctype))


def check_exclusive(flags, names):
    """Check if only one flag is set with exclusive flags.

    Raise a CommandError if not.

    Args:
        flags: An iterable of booleans to check.
        names: An iterable of flag names for the error message.
    """
    if sum(1 for e in flags if e) > 1:
        argstr = '/'.join('-' + e for e in names)
        raise cmdexc.CommandError("Only one of {} can be given!".format(
            argstr))


class register:  # pylint: disable=invalid-name

    """Decorator to register a new command handler.

    This could also be a function, but as a class (with a "wrong" name) it's
    much cleaner to implement.

    Attributes:
        _instance: The object from the object registry to be used as "self".
        _name: The name (as string) or names (as list) of the command.
        _kwargs: The arguments to pass to Command.
    """

    def __init__(self, *, instance=None, name=None, **kwargs):
        """Save decorator arguments.

        Gets called on parse-time with the decorator arguments.

        Args:
            See class attributes.
        """
        self._instance = instance
        self._name = name
        self._kwargs = kwargs

    def _get_names(self, func):
        """Get the name(s) which should be used for the current command.

        If the name hasn't been overridden explicitly, the function name is
        transformed.

        If it has been set, it can either be a string which is
        used directly, or an iterable.

        Args:
            func: The function to get the name of.

        Return:
            A list of names, with the main name being the first item.
        """
        if self._name is None:
            return [func.__name__.lower().replace('_', '-')]
        elif isinstance(self._name, str):
            return [self._name]
        else:
            return self._name

    def __call__(self, func):
        """Register the command before running the function.

        Gets called when a function should be decorated.

        Doesn't actually decorate anything, but creates a Command object and
        registers it in the cmd_dict.

        Args:
            func: The function to be decorated.

        Return:
            The original function (unmodified).
        """
        global aliases
        names = self._get_names(func)
        log.commands.vdebug("Registering command {}".format(names[0]))
        for name in names:
            if name in cmd_dict:
                raise ValueError("{} is already registered!".format(name))
        cmd = command.Command(name=names[0], instance=self._instance,
                              handler=func, **self._kwargs)
        for name in names:
            cmd_dict[name] = cmd
        aliases += names[1:]
        return func


class argument:  # pylint: disable=invalid-name

    """Decorator to customize an argument for @cmdutils.register.

    This could also be a function, but as a class (with a "wrong" name) it's
    much cleaner to implement.

    Attributes:
        _argname: The name of the argument to handle.
        _kwargs: Keyword arguments, valid ArgInfo members
    """

    def __init__(self, argname, **kwargs):
        self._argname = argname
        self._kwargs = kwargs

    def __call__(self, func):
        funcname = func.__name__

        if self._argname not in inspect.signature(func).parameters:
            raise ValueError("{} has no argument {}!".format(funcname,
                                                             self._argname))
        if not hasattr(func, 'qute_args'):
            func.qute_args = {}
        elif func.qute_args is None:
            raise ValueError("@cmdutils.argument got called above (after) "
                             "@cmdutils.register for {}!".format(funcname))

        func.qute_args[self._argname] = command.ArgInfo(**self._kwargs)
        return func
