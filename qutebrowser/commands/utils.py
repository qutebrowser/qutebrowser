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

import inspect
from collections import Iterable

import qutebrowser.utils.qt as qtutils
from qutebrowser.commands.command import Command
from qutebrowser.commands.exceptions import CommandError
from qutebrowser.utils.usertypes import KeyMode

cmd_dict = {}


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
        raise CommandError("Numeric argument is too large for internal {} "
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
        ValueError: If nothing was set or the value couldn't be converted to
                    an integer.
    """
    if count is not None and arg is not None:
        raise ValueError("Both count and argument given!")
    elif arg is not None:
        try:
            return int(arg)
        except ValueError:
            raise ValueError("Invalid number: {}".format(arg))
    elif count is not None:
        if countzero is not None and count == 0:
            return countzero
        else:
            return int(count)
    elif default is not None:
        return int(default)
    else:
        raise ValueError("Either count or argument have to be set!")


class register:  # pylint: disable=invalid-name

    """Decorator to register a new command handler.

    This could also be a function, but as a class (with a "wrong" name) it's
    much cleaner to implement.

    Attributes:
        instance: The instance to be used as "self", as a dotted string.
        name: The name (as string) or names (as list) of the command.
        nargs: A (minargs, maxargs) tuple of valid argument counts, or an int.
        split: Whether to split the arguments.
        hide: Whether to hide the command or not.
        completion: Which completion to use for arguments, as a list of
                    strings.
        modes/not_modes: List of modes to use/not use.
        needs_js: If javascript is needed for this command.
        debug: Whether this is a debugging command (only shown with --debug).
    """

    def __init__(self, instance=None, name=None, nargs=None, split=True,
                 hide=False, completion=None, modes=None, not_modes=None,
                 needs_js=False, debug=False):
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
        self.nargs = nargs
        self.instance = instance
        self.completion = completion
        self.modes = modes
        self.not_modes = not_modes
        self.needs_js = needs_js
        self.debug = debug
        if modes is not None:
            for m in modes:
                if not isinstance(m, KeyMode):
                    raise TypeError("Mode {} is no KeyMode member!".format(m))
        if not_modes is not None:
            for m in not_modes:
                if not isinstance(m, KeyMode):
                    raise TypeError("Mode {} is no KeyMode member!".format(m))

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
        # pylint: disable=no-member
        names = []
        if self.name is None:
            name = func.__name__.lower().replace('_', '-')
        else:
            name = self.name
        if isinstance(name, str):
            mainname = name
            names.append(name)
        else:
            mainname = name[0]
            names += name
        if mainname in cmd_dict:
            raise ValueError("{} is already registered!".format(name))
        argspec = inspect.getfullargspec(func)
        if 'self' in argspec.args and self.instance is None:
            raise ValueError("{} is a class method, but instance was not "
                             "given!".format(mainname))
        count, nargs = self._get_nargs_count(argspec)
        if func.__doc__ is not None:
            desc = func.__doc__.splitlines()[0].strip()
        else:
            desc = ""
        cmd = Command(name=mainname, split=self.split,
                      hide=self.hide, nargs=nargs, count=count, desc=desc,
                      instance=self.instance, handler=func,
                      completion=self.completion, modes=self.modes,
                      not_modes=self.not_modes, needs_js=self.needs_js,
                      debug=self.debug)
        for name in names:
            cmd_dict[name] = cmd
        return func

    def _get_nargs_count(self, spec):
        """Get the number of command-arguments and count-support for a func.

        Args:
            spec: A FullArgSpec as returned by inspect.

        Return:
            A (count, (minargs, maxargs)) tuple, with maxargs=None if there are
            infinite args. count is True if the function supports count, else
            False.

            Mapping from old nargs format to (minargs, maxargs):
                ?   (0, 1)
                N   (N, N)
                +   (1, None)
                *   (0, None)
        """
        # pylint: disable=unpacking-non-sequence
        # pylint: disable=no-member
        count = 'count' in spec.args
        # we assume count always has a default (and it should!)
        if self.nargs is not None:
            # If nargs is overriden, use that.
            if isinstance(self.nargs, Iterable):
                # Iterable (min, max)
                minargs, maxargs = self.nargs
            else:
                # Single int
                minargs, maxargs = self.nargs, self.nargs
        else:
            defaultcount = (len(spec.defaults) if spec.defaults is not None
                            else 0)
            argcount = len(spec.args)
            if 'self' in spec.args:
                argcount -= 1
            minargs = argcount - defaultcount
            if spec.varargs is not None:
                maxargs = None
            else:
                maxargs = argcount - int(count)  # -1 if count is defined
        return (count, (minargs, maxargs))
