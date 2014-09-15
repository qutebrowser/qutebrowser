# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Contains various command utils and a global command dict.

Module attributes:
    cmd_dict: A mapping from command-strings to command objects.
"""

from qutebrowser.utils import usertypes, qtutils, log
from qutebrowser.commands import command, cmdexc

cmd_dict = {}
aliases = []


def check_overflow(arg, ctype):
    """Check if the given argument is in bounds for the given type.

    Args:
        arg: The argument to check
        ctype: The C/Qt type to check as a string.

    Raise:
        CommandError if the argument is out of bounds.
        ValueError if the given ctype is unknown.
    """
    # FIXME we somehow should have nicer exceptions...
    try:
        qtutils.check_overflow(arg, ctype)
    except OverflowError:
        raise cmdexc.CommandError(
            "Numeric argument is too large for internal {} "
            "representation.".format(ctype))


def arg_or_count(arg, count, default=None, countzero=None):
    """Get a value based on an argument and count given to a command.

    If both arg and count are set, ValueError is raised.
    If only arg/count is set, it is used.
    If none is set, a default is returned or ValueError is raised.

    Args:
        arg: The argument given to a command.
        count: The count given to a command.
        countzero: Special value if count is 0.

    Return:
        The value to use.

    Raise:
        ValueError: If nothing was set.
    """
    if count is not None and arg is not None:
        raise ValueError("Both count and argument given!")
    elif arg is not None:
        return arg
    elif count is not None:
        if countzero is not None and count == 0:
            return countzero
        else:
            return count
    elif default is not None:
        return default
    else:
        raise ValueError("Either count or argument have to be set!")


class register:  # pylint: disable=invalid-name

    """Decorator to register a new command handler.

    This could also be a function, but as a class (with a "wrong" name) it's
    much cleaner to implement.

    Attributes:
        instance: The instance to be used as "self", as a dotted string.
        name: The name (as string) or names (as list) of the command.
        split: Whether to split the arguments.
        hide: Whether to hide the command or not.
        completion: Which completion to use for arguments, as a list of
                    strings.
        modes/not_modes: List of modes to use/not use.
        needs_js: If javascript is needed for this command.
        debug: Whether this is a debugging command (only shown with --debug).
        ignore_args: Whether to ignore the arguments of the function.
    """

    def __init__(self, instance=None, name=None, split=True, hide=False,
                 completion=None, modes=None, not_modes=None, needs_js=False,
                 debug=False, ignore_args=False):
        """Save decorator arguments.

        Gets called on parse-time with the decorator arguments.

        Args:
            See class attributes.
        """
        # pylint: disable=too-many-arguments
        if modes is not None and not_modes is not None:
            raise ValueError("Only modes or not_modes can be given!")
        self.name = name
        self.split = split
        self.hide = hide
        self.instance = instance
        self.completion = completion
        self.modes = modes
        self.not_modes = not_modes
        self.needs_js = needs_js
        self.debug = debug
        self.ignore_args = ignore_args
        if modes is not None:
            for m in modes:
                if not isinstance(m, usertypes.KeyMode):
                    raise TypeError("Mode {} is no KeyMode member!".format(m))
        if not_modes is not None:
            for m in not_modes:
                if not isinstance(m, usertypes.KeyMode):
                    raise TypeError("Mode {} is no KeyMode member!".format(m))

    def _get_names(self, func):
        """Get the name(s) which should be used for the current command.

        If the name hasn't been overridden explicitely, the function name is
        transformed.

        If it has been set, it can either be a string which is
        used directly, or an iterable.

        Args:
            func: The function to get the name of.

        Return:
            A list of names, with the main name being the first item.
        """
        if self.name is None:
            return [func.__name__.lower().replace('_', '-')]
        elif isinstance(self.name, str):
            return [self.name]
        else:
            return self.name

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
        cmd = command.Command(
            name=names[0], split=self.split, hide=self.hide,
            instance=self.instance, completion=self.completion,
            modes=self.modes, not_modes=self.not_modes, needs_js=self.needs_js,
            is_debug=self.debug, ignore_args=self.ignore_args, handler=func)
        for name in names:
            cmd_dict[name] = cmd
        aliases += names[1:]
        return func
