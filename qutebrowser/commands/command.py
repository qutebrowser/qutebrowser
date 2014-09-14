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

"""Contains the Command class, a skeleton for a command."""

import inspect

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWebKit import QWebSettings

from qutebrowser.commands import cmdexc, argparser
from qutebrowser.utils import log, utils, message, debug


class Command:

    """Base skeleton for a command.

    Attributes:
        name: The main name of the command.
        split: Whether to split the arguments.
        hide: Whether to hide the arguments or not.
        count: Whether the command supports a count, or not.
        desc: The description of the command.
        instance: How to get to the "self" argument of the handler.
                  A dotted string as viewed from app.py, or None.
        handler: The handler function to call.
        completion: Completions to use for arguments, as a list of strings.
        needs_js: Whether the command needs javascript enabled
        debug: Whether this is a debugging command (only shown with --debug).
        parser: The ArgumentParser to use to parse this command.
        type_conv: A mapping of conversion functions for arguments.
    """

    # TODO:
    # we should probably have some kind of typing / argument casting for args
    # this might be combined with help texts or so as well

    def __init__(self, name, split, hide, count, desc, instance, handler,
                 completion, modes, not_modes, needs_js, is_debug, parser,
                 type_conv, opt_args, pos_args):
        # I really don't know how to solve this in a better way, I tried.
        # pylint: disable=too-many-arguments,too-many-locals
        self.name = name
        self.split = split
        self.hide = hide
        self.count = count
        self.desc = desc
        self.instance = instance
        self.handler = handler
        self.completion = completion
        self.modes = modes
        self.not_modes = not_modes
        self.needs_js = needs_js
        self.debug = is_debug
        self.parser = parser
        self.type_conv = type_conv
        self.opt_args = opt_args
        self.pos_args = pos_args

    def _check_prerequisites(self):
        """Check if the command is permitted to run currently.

        Raise:
            PrerequisitesError if the command can't be called currently.
        """
        # We don't use modeman.instance() here to avoid a circular import
        # of qutebrowser.keyinput.modeman.
        curmode = QCoreApplication.instance().modeman.mode()
        if self.modes is not None and curmode not in self.modes:
            mode_names = '/'.join(mode.name for mode in self.modes)
            raise cmdexc.PrerequisitesError(
                "{}: This command is only allowed in {} mode.".format(
                    self.name, mode_names))
        elif self.not_modes is not None and curmode in self.not_modes:
            mode_names = '/'.join(mode.name for mode in self.not_modes)
            raise cmdexc.PrerequisitesError(
                "{}: This command is not allowed in {} mode.".format(
                    self.name, mode_names))
        if self.needs_js and not QWebSettings.globalSettings().testAttribute(
                QWebSettings.JavascriptEnabled):
            raise cmdexc.PrerequisitesError(
                "{}: This command needs javascript enabled.".format(self.name))

    def run(self, args=None, count=None):
        """Run the command.

        Note we don't catch CommandError here as it might happen async.

        Args:
            args: Arguments to the command.
            count: Command repetition count.
        """
        dbgout = ["command called:", self.name]
        if args:
            dbgout.append(str(args))
        if count is not None:
            dbgout.append("(count={})".format(count))
        log.commands.debug(' '.join(dbgout))

        posargs = []
        kwargs = {}
        app = QCoreApplication.instance()

        try:
            namespace = self.parser.parse_args(args)
        except argparser.ArgumentParserError as e:
            message.error('{}: {}'.format(self.name, e))
            return
        except argparser.ArgumentParserExit as e:
            log.commands.debug("argparser exited with status {}: {}".format(
                e.status, e))
            return

        signature = inspect.signature(self.handler)

        for i, param in enumerate(signature.parameters.values()):
            if i == 0 and self.instance is not None:
                # Special case for 'self'.
                assert param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
                if self.instance == '':
                    obj = app
                else:
                    obj = utils.dotted_getattr(app, self.instance)
                posargs.append(obj)
                continue
            elif param.name == 'count':
                # Special case for 'count'.
                if not self.count:
                    raise TypeError("{}: count argument given with a command "
                                    "which does not support count!".format(
                                    self.name))
                if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                    if count is not None:
                        posargs.append(count)
                    else:
                        posargs.append(param.default)
                elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                    if count is not None:
                        kwargs['count'] = count
                else:
                    raise TypeError("{}: invalid parameter type {} for "
                                    "argument 'count'!".format(
                                        self.name, param.kind))
                continue
            value = getattr(namespace, param.name)
            if param.name in self.type_conv:
                # We convert enum types after getting the values from
                # argparse, because argparse's choices argument is
                # processed after type conversation, which is not what we
                # want.
                value = self.type_conv[param.name](value)
            if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                posargs.append(value)
            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                posargs += value
            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                kwargs[param.name] = value
            else:
                raise TypeError("{}: Invalid parameter type {} for argument "
                                "'{}'!".format(
                                    self.name, param.kind, param.name))
        self._check_prerequisites()
        log.commands.debug('Calling {}'.format(
            debug.format_call(self.handler, posargs, kwargs)))
        self.handler(*posargs, **kwargs)
