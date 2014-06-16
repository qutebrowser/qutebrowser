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

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWebKit import QWebSettings

from qutebrowser.commands.exceptions import (ArgumentCountError,
                                             PrerequisitesError)
from qutebrowser.utils.misc import dotted_getattr
from qutebrowser.utils.log import commands as logger


class Command:

    """Base skeleton for a command.

    Attributes:
        name: The main name of the command.
        split: Whether to split the arguments.
        hide: Whether to hide the arguments or not.
        nargs: A (minargs, maxargs) tuple, maxargs = None if there's no limit.
        count: Whether the command supports a count, or not.
        desc: The description of the command.
        instance: How to get to the "self" argument of the handler.
                  A dotted string as viewed from app.py, or None.
        handler: The handler function to call.
        completion: Completions to use for arguments, as a list of strings.
        needs_js: Whether the command needs javascript enabled
        debug: Whether this is a debugging command (only shown with --debug).
    """

    # TODO:
    # we should probably have some kind of typing / argument casting for args
    # this might be combined with help texts or so as well

    def __init__(self, name, split, hide, nargs, count, desc, instance,
                 handler, completion, modes, not_modes, needs_js, debug):
        # I really don't know how to solve this in a better way, I tried.
        # pylint: disable=too-many-arguments
        super().__init__()
        self.name = name
        self.split = split
        self.hide = hide
        self.nargs = nargs
        self.count = count
        self.desc = desc
        self.instance = instance
        self.handler = handler
        self.completion = completion
        self.modes = modes
        self.not_modes = not_modes
        self.needs_js = needs_js
        self.debug = debug

    def check(self, args):
        """Check if the argument count is valid and the command is permitted.

        Args:
            args: The supplied arguments

        Raise:
            ArgumentCountError if the argument count is wrong.
            PrerequisitesError if the command can't be called currently.
        """
        # We don't use modeman.instance() here to avoid a circular import
        # of qutebrowser.keyinput.modeman.
        curmode = QCoreApplication.instance().modeman.mode
        if self.modes is not None and curmode not in self.modes:
            raise PrerequisitesError("{}: This command is only allowed in {} "
                                     "mode.".format(self.name,
                                                    '/'.join(self.modes)))
        elif self.not_modes is not None and curmode in self.not_modes:
            raise PrerequisitesError("{}: This command is not allowed in {} "
                                     "mode.".format(self.name,
                                                    '/'.join(self.not_modes)))
        if self.needs_js and not QWebSettings.globalSettings().testAttribute(
                QWebSettings.JavascriptEnabled):
            raise PrerequisitesError("{}: This command needs javascript "
                                     "enabled.".format(self.name))
        if self.nargs[1] is None and self.nargs[0] <= len(args):
            pass
        elif self.nargs[0] <= len(args) <= self.nargs[1]:
            pass
        else:
            if self.nargs[0] == self.nargs[1]:
                argcnt = str(self.nargs[0])
            elif self.nargs[1] is None:
                argcnt = '{}-inf'.format(self.nargs[0])
            else:
                argcnt = '{}-{}'.format(self.nargs[0], self.nargs[1])
            raise ArgumentCountError("{}: {} args expected, but got {}".format(
                self.name, argcnt, len(args)))

    def run(self, args=None, count=None):
        """Run the command.

        Note we don't catch CommandError here as it might happen async.

        Args:
            args: Arguments to the command.
            count: Command repetition count.
        """
        dbgout = ["command called:", self.name]
        if args:
            dbgout += args
        if count is not None:
            dbgout.append("(count={})".format(count))
        logger.debug(' '.join(dbgout))

        kwargs = {}
        app = QCoreApplication.instance()

        if self.instance is not None:
            # Add the 'self' parameter.
            if self.instance == '':
                obj = app
            else:
                obj = dotted_getattr(app, self.instance)
            args.insert(0, obj)

        if count is not None and self.count:
            kwargs = {'count': count}

        self.handler(*args, **kwargs)
