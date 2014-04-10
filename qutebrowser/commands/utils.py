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

"""Contains various command utils and a global command dict."""

import inspect
from collections import Iterable

from qutebrowser.commands.command import Command

# A mapping from command-strings to command objects.
cmd_dict = {}


class register:

    """Decorator to register a new command handler.

    This could also be a function, but as a class (with a "wrong" name) it's
    much cleaner to implement.

    Attributes:
        instance: The instance to be used as "self", as a dotted string.
        name: The name (as string) or names (as list) of the command.
        nargs: A (minargs, maxargs) tuple of valid argument counts, or an int.
        split_args: Whether to split the arguments or not.
        hide: Whether to hide the command or not.
        completion: Which completion to use for arguments, as a list of
                    strings.
    """

    def __init__(self, instance=None, name=None, nargs=None, split_args=True,
                 hide=False, completion=None):
        """Save decorator arguments.

        Gets called on parse-time with the decorator arguments.

        Arguments:
            See class attributes.
        """
        self.name = name
        self.split_args = split_args
        self.hide = hide
        self.nargs = nargs
        self.instance = instance
        self.completion = completion

    def __call__(self, func):
        """Register the command before running the function.

        Gets called when a function should be decorated.

        Doesn't actually decorate anything, but creates a Command object and
        registers it in the cmd_dict.

        Arguments:
            func: The function to be decorated.

        Return:
            The original function (unmodified).
        """
        # FIXME: only register commands once
        names = []
        name = func.__name__.lower() if self.name is None else self.name
        if isinstance(name, str):
            mainname = name
            names.append(name)
        else:
            mainname = name[0]
            names += name
        count, nargs = self._get_nargs_count(func)
        desc = func.__doc__.splitlines()[0].strip().rstrip('.')
        cmd = Command(name=mainname, split_args=self.split_args,
                      hide=self.hide, nargs=nargs, count=count, desc=desc,
                      instance=self.instance, handler=func,
                      completion=self.completion)
        for name in names:
            cmd_dict[name] = cmd
        return func

    def _get_nargs_count(self, func):
        """Get the number of command-arguments and count-support for a func.

        Args:
            func: The function to get the argcount for.

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
        # pylint: disable=no-member
        # pylint: disable=unpacking-non-sequence
        # We could use inspect.signature maybe, but that's python >= 3.3 only.
        spec = inspect.getfullargspec(func)
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
