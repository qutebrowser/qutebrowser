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

"""Contains the Command class, a skeleton for a command."""

import inspect
import collections
import traceback

from qutebrowser.commands import cmdexc, argparser
from qutebrowser.utils import (log, utils, message, docutils, objreg,
                               usertypes, typing)
from qutebrowser.utils import debug as debug_utils


class ArgInfo:

    """Information about an argument."""

    def __init__(self, win_id=False, count=False, hide=False, metavar=None,
                 flag=None, completion=None, choices=None):
        if win_id and count:
            raise TypeError("Argument marked as both count/win_id!")
        self.win_id = win_id
        self.count = count
        self.flag = flag
        self.hide = hide
        self.metavar = metavar
        self.completion = completion
        self.choices = choices

    def __eq__(self, other):
        return (self.win_id == other.win_id and
                self.count == other.count and
                self.flag == other.flag and
                self.hide == other.hide and
                self.metavar == other.metavar and
                self.completion == other.completion and
                self.choices == other.choices)

    def __repr__(self):
        return utils.get_repr(self, win_id=self.win_id, count=self.count,
                              flag=self.flag, hide=self.hide,
                              metavar=self.metavar, completion=self.completion,
                              choices=self.choices, constructor=True)


class Command:

    """Base skeleton for a command.

    Attributes:
        name: The main name of the command.
        maxsplit: The maximum amount of splits to do for the commandline, or
                  None.
        hide: Whether to hide the arguments or not.
        deprecated: False, or a string to describe why a command is deprecated.
        desc: The description of the command.
        handler: The handler function to call.
        debug: Whether this is a debugging command (only shown with --debug).
        parser: The ArgumentParser to use to parse this command.
        flags_with_args: A list of flags which take an argument.
        no_cmd_split: If true, ';;' to split sub-commands is ignored.
        backend: Which backend the command works with (or None if it works with
                 both)
        no_replace_variables: Don't replace variables like {url}
        _qute_args: The saved data from @cmdutils.argument
        _modes: The modes the command can be executed in.
        _count: The count set for the command.
        _instance: The object to bind 'self' to.
        _scope: The scope to get _instance for in the object registry.
    """

    def __init__(self, *, handler, name, instance=None, maxsplit=None,
                 hide=False, modes=None, not_modes=None, debug=False,
                 ignore_args=False, deprecated=False, no_cmd_split=False,
                 star_args_optional=False, scope='global', backend=None,
                 no_replace_variables=False):
        # I really don't know how to solve this in a better way, I tried.
        # pylint: disable=too-many-locals
        if modes is not None and not_modes is not None:
            raise ValueError("Only modes or not_modes can be given!")
        if modes is not None:
            for m in modes:
                if not isinstance(m, usertypes.KeyMode):
                    raise TypeError("Mode {} is no KeyMode member!".format(m))
            self._modes = set(modes)
        elif not_modes is not None:
            for m in not_modes:
                if not isinstance(m, usertypes.KeyMode):
                    raise TypeError("Mode {} is no KeyMode member!".format(m))
            self._modes = set(usertypes.KeyMode).difference(not_modes)
        else:
            self._modes = set(usertypes.KeyMode)
        if scope != 'global' and instance is None:
            raise ValueError("Setting scope without setting instance makes "
                             "no sense!")

        self.name = name
        self.maxsplit = maxsplit
        self.hide = hide
        self.deprecated = deprecated
        self._instance = instance
        self._scope = scope
        self._star_args_optional = star_args_optional
        self.debug = debug
        self.ignore_args = ignore_args
        self.handler = handler
        self.no_cmd_split = no_cmd_split
        self.backend = backend
        self.no_replace_variables = no_replace_variables

        self.docparser = docutils.DocstringParser(handler)
        self.parser = argparser.ArgumentParser(
            name, description=self.docparser.short_desc,
            epilog=self.docparser.long_desc)
        self.parser.add_argument('-h', '--help', action=argparser.HelpAction,
                                 default=argparser.SUPPRESS, nargs=0,
                                 help=argparser.SUPPRESS)
        self._check_func()
        self.opt_args = collections.OrderedDict()
        self.namespace = None
        self._count = None
        self.pos_args = []
        self.desc = None
        self.flags_with_args = []

        # This is checked by future @cmdutils.argument calls so they fail
        # (as they'd be silently ignored otherwise)
        self._qute_args = getattr(self.handler, 'qute_args', {})
        self.handler.qute_args = None

        self._inspect_func()

    def _check_prerequisites(self, win_id):
        """Check if the command is permitted to run currently.

        Args:
            win_id: The window ID the command is run in.
        """
        mode_manager = objreg.get('mode-manager', scope='window',
                                  window=win_id)
        self.validate_mode(mode_manager.mode)

        used_backend = usertypes.arg2backend[objreg.get('args').backend]
        if self.backend is not None and used_backend != self.backend:
            raise cmdexc.PrerequisitesError(
                "{}: Only available with {} "
                "backend.".format(self.name, self.backend.name))

        if self.deprecated:
            message.warning('{} is deprecated - {}'.format(self.name,
                                                           self.deprecated))

    def _check_func(self):
        """Make sure the function parameters don't violate any rules."""
        signature = inspect.signature(self.handler)
        if 'self' in signature.parameters and self._instance is None:
            raise TypeError("{} is a class method, but instance was not "
                            "given!".format(self.name[0]))
        elif 'self' not in signature.parameters and self._instance is not None:
            raise TypeError("{} is not a class method, but instance was "
                            "given!".format(self.name[0]))
        elif any(param.kind == inspect.Parameter.VAR_KEYWORD
                 for param in signature.parameters.values()):
            raise TypeError("{}: functions with varkw arguments are not "
                            "supported!".format(self.name[0]))

    def get_arg_info(self, param):
        """Get an ArgInfo tuple for the given inspect.Parameter."""
        return self._qute_args.get(param.name, ArgInfo())

    def get_pos_arg_info(self, pos):
        """Get an ArgInfo tuple for the given positional parameter."""
        name = self.pos_args[pos][0]
        return self._qute_args.get(name, ArgInfo())

    def _inspect_special_param(self, param):
        """Check if the given parameter is a special one.

        Args:
            param: The inspect.Parameter to handle.

        Return:
            True if the parameter is special, False otherwise.
        """
        arg_info = self.get_arg_info(param)
        if arg_info.count:
            if param.default is inspect.Parameter.empty:
                raise TypeError("{}: handler has count parameter "
                                "without default!".format(self.name))
            return True
        elif arg_info.win_id:
            return True

    def _inspect_func(self):
        """Inspect the function to get useful informations from it.

        Sets instance attributes (desc, type_conv, name_conv) based on the
        informations.

        Return:
            How many user-visible arguments the command has.
        """
        signature = inspect.signature(self.handler)
        doc = inspect.getdoc(self.handler)
        if doc is not None:
            self.desc = doc.splitlines()[0].strip()
        else:
            self.desc = ""

        if not self.ignore_args:
            for param in signature.parameters.values():
                # https://docs.python.org/3/library/inspect.html#inspect.Parameter.kind
                # "Python has no explicit syntax for defining positional-only
                # parameters, but many built-in and extension module functions
                # (especially those that accept only one or two parameters)
                # accept them."
                assert param.kind != inspect.Parameter.POSITIONAL_ONLY
                if param.name == 'self':
                    continue
                if self._inspect_special_param(param):
                    continue
                if (param.kind == inspect.Parameter.KEYWORD_ONLY and
                        param.default is inspect.Parameter.empty):
                    raise TypeError("{}: handler has keyword only argument "
                                    "{!r} without default!".format(self.name,
                                                                   param.name))
                typ = self._get_type(param)
                is_bool = typ is bool
                kwargs = self._param_to_argparse_kwargs(param, is_bool)
                args = self._param_to_argparse_args(param, is_bool)
                callsig = debug_utils.format_call(
                    self.parser.add_argument, args, kwargs,
                    full=False)
                log.commands.vdebug('Adding arg {} of type {} -> {}'.format(
                    param.name, typ, callsig))
                self.parser.add_argument(*args, **kwargs)
        return signature.parameters.values()

    def _param_to_argparse_kwargs(self, param, is_bool):
        """Get argparse keyword arguments for a parameter.

        Args:
            param: The inspect.Parameter object to get the args for.
            is_bool: Whether the parameter is a boolean.

        Return:
            A kwargs dict.
        """
        kwargs = {}

        try:
            kwargs['help'] = self.docparser.arg_descs[param.name]
        except KeyError:
            pass

        kwargs['dest'] = param.name

        arg_info = self.get_arg_info(param)

        if is_bool:
            kwargs['action'] = 'store_true'
        else:
            if arg_info.metavar is not None:
                kwargs['metavar'] = arg_info.metavar
            else:
                kwargs['metavar'] = argparser.arg_name(param.name)

        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            kwargs['nargs'] = '*' if self._star_args_optional else '+'
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            kwargs['default'] = param.default
        elif not is_bool and param.default is not inspect.Parameter.empty:
            kwargs['default'] = param.default
            kwargs['nargs'] = '?'
        return kwargs

    def _param_to_argparse_args(self, param, is_bool):
        """Get argparse positional arguments for a parameter.

        Args:
            param: The inspect.Parameter object to get the args for.
            is_bool: Whether the parameter is a boolean.

        Return:
            A list of args.
        """
        args = []
        name = argparser.arg_name(param.name)
        arg_info = self.get_arg_info(param)

        if arg_info.flag is not None:
            shortname = arg_info.flag
        else:
            shortname = name[0]

        if len(shortname) != 1:
            raise ValueError("Flag '{}' of parameter {} (command {}) must be "
                             "exactly 1 char!".format(shortname, name,
                                                      self.name))
        if is_bool or param.kind == inspect.Parameter.KEYWORD_ONLY:
            long_flag = '--{}'.format(name)
            short_flag = '-{}'.format(shortname)
            args.append(long_flag)
            args.append(short_flag)
            self.opt_args[param.name] = long_flag, short_flag
            if not is_bool:
                self.flags_with_args += [short_flag, long_flag]
        else:
            if not arg_info.hide:
                self.pos_args.append((param.name, name))
        return args

    def _get_type(self, param):
        """Get the type of an argument from its default value or annotation.

        Args:
            param: The inspect.Parameter to look at.
        """
        arginfo = self.get_arg_info(param)
        if param.annotation is not inspect.Parameter.empty:
            return param.annotation
        elif param.default not in [None, inspect.Parameter.empty]:
            return type(param.default)
        elif arginfo.count or arginfo.win_id or param.kind in [
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD]:
            return None
        else:
            return str

    def _get_self_arg(self, win_id, param, args):
        """Get the self argument for a function call.

        Arguments:
            win_id: The window id this command should be executed in.
            param: The count parameter.
            args: The positional argument list. Gets modified directly.
        """
        assert param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        if self._scope == 'global':
            tab_id = None
            win_id = None
        elif self._scope == 'tab':
            tab_id = 'current'
        elif self._scope == 'window':
            tab_id = None
        else:
            raise ValueError("Invalid scope {}!".format(self._scope))
        obj = objreg.get(self._instance, scope=self._scope, window=win_id,
                         tab=tab_id)
        args.append(obj)

    def _get_count_arg(self, param, args, kwargs):
        """Add the count argument to a function call.

        Arguments:
            param: The count parameter.
            args: The positional argument list. Gets modified directly.
            kwargs: The keyword argument dict. Gets modified directly.
        """
        if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            if self._count is not None:
                args.append(self._count)
            else:
                args.append(param.default)
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            if self._count is not None:
                kwargs[param.name] = self._count
        else:
            raise TypeError("{}: invalid parameter type {} for argument "
                            "{!r}!".format(self.name, param.kind, param.name))

    def _get_win_id_arg(self, win_id, param, args, kwargs):
        """Add the win_id argument to a function call.

        Arguments:
            win_id: The window ID to add.
            param: The count parameter.
            args: The positional argument list. Gets modified directly.
            kwargs: The keyword argument dict. Gets modified directly.
        """
        if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            args.append(win_id)
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            kwargs[param.name] = win_id
        else:
            raise TypeError("{}: invalid parameter type {} for argument "
                            "{!r}!".format(self.name, param.kind, param.name))

    def _get_param_value(self, param):
        """Get the converted value for an inspect.Parameter."""
        value = getattr(self.namespace, param.name)
        typ = self._get_type(param)

        if isinstance(typ, tuple):
            raise TypeError("{}: Legacy tuple type annotation!".format(
                self.name))
        elif type(typ) is type(typing.Union):  # flake8: disable=E721
            # this is... slightly evil, I know
            # We also can't use isinstance here because typing.Union doesn't
            # support that.
            # pylint: disable=no-member,useless-suppression
            try:
                types = list(typ.__union_params__)
            except AttributeError:
                types = list(typ.__args__)
            # pylint: enable=no-member,useless-suppression
            if param.default is not inspect.Parameter.empty:
                types.append(type(param.default))
            choices = self.get_arg_info(param).choices
            value = argparser.multitype_conv(param, types, value,
                                             str_choices=choices)
        elif typ is str:
            choices = self.get_arg_info(param).choices
            value = argparser.type_conv(param, typ, value, str_choices=choices)
        elif typ is bool:  # no type conversion for flags
            assert isinstance(value, bool)
        elif typ is None:
            pass
        else:
            value = argparser.type_conv(param, typ, value)

        return value

    def _get_call_args(self, win_id):
        """Get arguments for a function call.

        Args:
            win_id: The window id this command should be executed in.

        Return:
            An (args, kwargs) tuple.
        """
        args = []
        kwargs = {}
        signature = inspect.signature(self.handler)

        if self.ignore_args:
            if self._instance is not None:
                param = list(signature.parameters.values())[0]
                self._get_self_arg(win_id, param, args)
            return args, kwargs

        for i, param in enumerate(signature.parameters.values()):
            arg_info = self.get_arg_info(param)
            if i == 0 and self._instance is not None:
                # Special case for 'self'.
                self._get_self_arg(win_id, param, args)
                continue
            elif arg_info.count:
                # Special case for count parameter.
                self._get_count_arg(param, args, kwargs)
                continue
            # elif arg_info.win_id:
            elif arg_info.win_id:
                # Special case for win_id parameter.
                self._get_win_id_arg(win_id, param, args, kwargs)
                continue
            value = self._get_param_value(param)
            if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                args.append(value)
            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                if value is not None:
                    args += value
            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                kwargs[param.name] = value
            else:
                raise TypeError("{}: Invalid parameter type {} for argument "
                                "'{}'!".format(
                                    self.name, param.kind, param.name))
        return args, kwargs

    def run(self, win_id, args=None, count=None):
        """Run the command.

        Note we don't catch CommandError here as it might happen async.

        Args:
            win_id: The window ID the command is run in.
            args: Arguments to the command.
            count: Command repetition count.
        """
        dbgout = ["command called:", self.name]
        if args:
            dbgout.append(str(args))
        elif args is None:
            args = []

        if count is not None:
            dbgout.append("(count={})".format(count))
        log.commands.debug(' '.join(dbgout))
        try:
            self.namespace = self.parser.parse_args(args)
        except argparser.ArgumentParserError as e:
            message.error('{}: {}'.format(self.name, e),
                          stack=traceback.format_exc())
            return
        except argparser.ArgumentParserExit as e:
            log.commands.debug("argparser exited with status {}: {}".format(
                e.status, e))
            return
        self._count = count
        self._check_prerequisites(win_id)
        posargs, kwargs = self._get_call_args(win_id)
        log.commands.debug('Calling {}'.format(
            debug_utils.format_call(self.handler, posargs, kwargs)))
        self.handler(*posargs, **kwargs)

    def validate_mode(self, mode):
        """Raise cmdexc.PrerequisitesError unless allowed in the given mode.

        Args:
            mode: The usertypes.KeyMode to check.
        """
        if mode not in self._modes:
            mode_names = '/'.join(sorted(m.name for m in self._modes))
            raise cmdexc.PrerequisitesError(
                "{}: This command is only allowed in {} mode, not {}.".format(
                    self.name, mode_names, mode.name))
