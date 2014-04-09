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

"""Contains the Command class, a skeleton for a command."""

import logging

from qutebrowser.commands.exceptions import ArgumentCountError

from PyQt5.QtCore import pyqtSignal, QObject


class Command(QObject):

    """Base skeleton for a command.

    Attributes:
        name: The main name of the command.
        split_args: Whether to split the arguments or not.
        hide: Whether to hide the arguments or not.
        nargs: A (minargs, maxargs) tuple, maxargs = None if there's no limit.
        count: Whether the command supports a count, or not.
        desc: The description of the command.
        instance: How to get to the "self" argument of the handler.
                  A dotted string as viewed from app.py, or None.
        handler: The handler function to call.
        completion: Completions to use for arguments, as a list of strings.

    Signals:
        signal: Gets emitted when something should be called via handle_command
                from the app.py context.

    """

    # FIXME:
    # we should probably have some kind of typing / argument casting for args
    # this might be combined with help texts or so as well

    signal = pyqtSignal(tuple)

    def __init__(self, name, split_args, hide, nargs, count, desc, instance,
                 handler, completion):
        super().__init__()
        self.name = name
        self.split_args = split_args
        self.hide = hide
        self.nargs = nargs
        self.count = count
        self.desc = desc
        self.instance = instance
        self.handler = handler
        self.completion = completion

    def check(self, args):
        """Check if the argument count is valid.

        Raise ArgumentCountError if not.

        Args:
            args: The supplied arguments

        Raise:
            ArgumentCountError if the argument count is wrong.

        """
        if self.nargs[0] <= len(args) <= self.nargs[1]:
            pass
        else:
            raise ArgumentCountError("{}-{} args expected, but got {}".format(
                self.nargs[0],
                self.nargs[1] if self.nargs[1] is not None else 'inf',
                len(args)))

    def run(self, args=None, count=None):
        """Run the command.

        Args:
            args: Arguments to the command.
            count: Command repetition count.

        Emit:
            signal: When the command has an instance and should be handled from
                    the app.py context.

        """
        dbgout = ["command called:", self.name]
        if args:
            dbgout += args
        if count is not None:
            dbgout.append("(count={})".format(count))
        logging.debug(' '.join(dbgout))

        if self.instance is not None and self.count and count is not None:
            self.signal.emit((self.instance, self.handler.__name__, count,
                              args))
        elif self.instance is not None:
            self.signal.emit((self.instance, self.handler.__name__, None,
                              args))
        elif count is not None and self.count:
            return self.handler(*args, count=count)
        else:
            return self.handler(*args)
