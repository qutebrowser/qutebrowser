"""Contains the Command class, a skeleton for a command."""

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

import logging

from PyQt5.QtCore import QObject, pyqtSignal

from qutebrowser.commands.exceptions import ArgumentCountError


class Command(QObject):
    """Base skeleton for a command.

    See the module documentation for qutebrowser.commands.commands for details.
    """

    # FIXME:
    # we should probably have some kind of typing / argument casting for args
    # this might be combined with help texts or so as well

    nargs = 0
    name = None
    mainname = None
    signal = None
    count = False
    split_args = True
    signal = pyqtSignal(tuple)
    hide = False

    def __init__(self):
        super().__init__()
        if self.name is None:
            self.name = self.__class__.__name__.lower()
        if isinstance(self.name, str):
            self.mainname = self.name
        else:
            self.mainname = self.name[0]

    def check(self, args):
        """Check if the argument count is valid. Raise ArgumentCountError if
        not.
        """
        if ((isinstance(self.nargs, int) and len(args) != self.nargs) or
                (self.nargs == '?' and len(args) > 1) or
                (self.nargs == '+' and len(args) < 1)):
            # for nargs == '*', anything is okay
            raise ArgumentCountError

    def run(self, args=None, count=None):
        """Runs the command.

        args -- Arguments to the command.
        count -- Command repetition count.
        """
        dbgout = ["command called:", self.mainname]
        if args:
            dbgout += args
        if count is not None:
            dbgout.append("(count={})".format(count))
        logging.debug(' '.join(dbgout))

        argv = [self.mainname]
        if args is not None:
            argv += args
        self.signal.emit((count, argv))
