# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import typing

import attr

from qutebrowser.api import cmdutils
from qutebrowser.commands import cmdexc, argparser
from qutebrowser.utils import log, message, docutils, objreg, usertypes, utils
from qutebrowser.utils import debug as debug_utils
from qutebrowser.misc import objects


@attr.s
class ArgInfo:

    """Information about an argument."""

    value = attr.ib(None)
    hide = attr.ib(False)
    metavar = attr.ib(None)
    flag = attr.ib(None)
    completion = attr.ib(None)
    choices = attr.ib(None)


class Command:

    """Base skeleton for a command.

    Attributes:
        name: The main name of the command.
        maxsplit: The maximum amount of splits to do for the commandline, or
                  None.
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
        modes: The modes the command can be executed in.
        _qute_args: The saved data from @cmdutils.argument
        _count: The count set for the command.
        _instance: The object to bind 'self' to.
        _scope: The scope to get _instance for in the object registry.
    """

    # CommandValue values which need a count
    COUNT_COMMAND_VALUES = [usertypes.CommandValue.count,
                            usertypes.CommandValue.count_tab]

    def __init__(self, *, handler, name, instance=None, maxsplit=None,
                 modes=None, not_modes=None, debug=False, deprecated=False,
                 no_cmd_split=False, star_args_optional=False, scope='global',
                 backend=None, no_replace_variables=False):
        if modes is not None and not_modes is not None:
            raise ValueError("Only modes or not_modes can be given!")
        if modes is not None:
            for m in modes:
                if not isinstance(m, usertypes.KeyMode):
                    raise TypeError("Mode {} is no KeyMode member!".format(m))
            self.modes = set(modes)
        elif not_modes is not None:
            for m in not_modes:
                if not isinstance(m, usertypes.KeyMode):
                    raise TypeError("Mode {} is no KeyMode member!".format(m))
            self.modes = set(usertypes.KeyMode).difference(not_modes)
        else:
            self.modes = set(usertypes.KeyMode)
        if scope != 'global' and instance is None:
            raise ValueError("Setting scope without setting instance makes "
                             "no sense!")

        self.name = name
        self.maxsplit = maxsplit
        self.deprecated = deprecated
        self._instance = instance
        self._scope = scope
        self._star_args_optional = star_args_optional
        self.debug = debug
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
        self.opt_args = collections.OrderedDict(
        )  # type: typing.MutableMapping[str, typing.Tuple[str, str]]
        self.namespace = None
        self._count = None
        self.pos_args = [
        ]  # type: typing.MutableSequence[typing.Tuple[str, str]]
        self.flags_with_args = []  # type: typing.MutableSequence[str]
        self._has_vararg = False

        # This is checked by future @cmdutils.argument calls so they fail
        # (as they'd be silently ignored otherwise)
        self._qute_args = getattr(self.handler, 'qute_args', {})
        self.handler.qute_args = None

        self._check_func()
        self._inspect_func()

    def _check_prerequisites(self, win_id):
        """Check if the command is permitted to run currently.

        Args:
            win_id: The window ID the command is run in.
        """
        from qutebrowser.keyinput import modeman
        mode_manager = modeman.instance(win_id)
        self.validate_mode(mode_manager.mode)

        if self.backend is not None and objects.backend != self.backend:
            raise cmdexc.PrerequisitesError(
                "{}: Only available with {} "
                "backend.".format(self.name, self.backend.name))

        if self.deprecated:
            message.warning('{} is deprecated - {}'.format(self.name,
                                                           self.deprecated))

    def _check_func(self):
        """Make sure the function parameters don't violate any rules."""
        signature = inspect.signature(self.handler)
        if 'self' in signature.parameters:
            if self._instance is None:
                raise TypeError("{} is a class method, but instance was not "
                                "given!".format(self.name))
            arg_info = self.get_arg_info(signature.parameters['self'])
            if arg_info.value is not None:
                raise TypeError("{}: Can't fill 'self' with value!"
                                .format(self.name))
        elif 'self' not in signature.parameters and self._instance is not None:
            raise TypeError("{} is not a class method, but instance was "
                            "given!".format(self.name))
        elif any(param.kind == inspect.Parameter.VAR_KEYWORD
                 for param in signature.parameters.values()):
            raise TypeError("{}: functions with varkw arguments are not "
                            "supported!".format(self.name))

    def get_arg_info(self, param):
        """Get an ArgInfo tuple for the given inspect.Parameter."""
        return self._qute_args.get(param.name, ArgInfo())

    def get_pos_arg_info(self, pos):
        """Get an ArgInfo tuple for the given positional parameter."""
        if pos >= len(self.pos_args) and self._has_vararg:
            pos = len(self.pos_args) - 1
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
        if arg_info.value is None:
            return False
        elif arg_info.value == usertypes.CommandValue.count:
            if param.default is inspect.Parameter.empty:
                raise TypeError("{}: handler has count parameter "
                                "without default!".format(self.name))
            return True
        elif isinstance(arg_info.value, usertypes.CommandValue):
            return True
        else:
            raise TypeError("{}: Invalid value={!r} for argument '{}'!"
                            .format(self.name, arg_info.value, param.name))
        raise utils.Unreachable

    def _inspect_func(self):
        """Inspect the function to get useful information from it.

        Sets instance attributes (desc, type_conv, name_conv) based on the
        information.

        Return:
            How many user-visible arguments the command has.
        """
        signature = inspect.signature(self.handler)
        doc = inspect.getdoc(self.handler)
        if doc is not None:
            self.desc = doc.splitlines()[0].strip()
        else:
            self.desc = ""

        for param in signature.parameters.values():
            # https://docs.python.org/3/library/inspect.html#inspect.Parameter.kind
            # "Python has no explicit syntax for defining positional-only
            # parameters, but many built-in and extension module functions
            # (especially those that accept only one or two parameters) accept
            # them."
            assert param.kind != inspect.Parameter.POSITIONAL_ONLY
            if param.name == 'self':
                continue
            if self._inspect_special_param(param):
                continue
            if (param.kind == inspect.Parameter.KEYWORD_ONLY and
                    param.default is inspect.Parameter.empty):
                raise TypeError("{}: handler has keyword only argument {!r} "
                                "without default!".format(
                                    self.name, param.name))
            typ = self._get_type(param)
            is_bool = typ is bool
            kwargs = self._param_to_argparse_kwargs(param, is_bool)
            args = self._param_to_argparse_args(param, is_bool)
            callsig = debug_utils.format_call(self.parser.add_argument, args,
                                              kwargs, full=False)
            log.commands.vdebug(  # type: ignore[attr-defined]
                'Adding arg {} of type {} -> {}'
                .format(param.name, typ, callsig))
            self.parser.add_argument(*args, **kwargs)
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                self._has_vararg = True
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

        assert not arg_info.value, name

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
        if arginfo.value:
            # Filled values are passed 1:1
            return None
        elif param.kind in [inspect.Parameter.VAR_POSITIONAL,
                            inspect.Parameter.VAR_KEYWORD]:
            # For *args/**kwargs we only support strings
            assert param.annotation in [inspect.Parameter.empty, str], param
            return None
        elif param.annotation is not inspect.Parameter.empty:
            return param.annotation
        elif param.default not in [None, inspect.Parameter.empty]:
            return type(param.default)
        else:
            return str

    def _get_objreg(self, *, win_id, name, scope):
        """Get an object from the objreg."""
        if scope == 'global':
            tab_id = None
            win_id = None
        elif scope == 'tab':
            tab_id = 'current'
        elif scope == 'window':
            tab_id = None
        else:
            raise ValueError("Invalid scope {}!".format(scope))
        return objreg.get(name, scope=scope, window=win_id, tab=tab_id,
                          from_command=True)

    def _add_special_arg(self, *, value, param, args, kwargs):
        """Add a special argument value to a function call.

        Arguments:
            value: The value to add.
            param: The parameter being filled.
            args: The positional argument list. Gets modified directly.
            kwargs: The keyword argument dict. Gets modified directly.
        """
        if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            args.append(value)
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            kwargs[param.name] = value
        else:
            raise TypeError("{}: invalid parameter type {} for argument "
                            "{!r}!".format(self.name, param.kind, param.name))

    def _add_count_tab(self, *, win_id, param, args, kwargs):
        """Add the count_tab widget argument."""
        tabbed_browser = self._get_objreg(
            win_id=win_id, name='tabbed-browser', scope='window')

        if self._count is None:
            tab = tabbed_browser.widget.currentWidget()
        elif 1 <= self._count <= tabbed_browser.widget.count():
            cmdutils.check_overflow(self._count + 1, 'int')
            tab = tabbed_browser.widget.widget(self._count - 1)
        else:
            tab = None

        self._add_special_arg(value=tab, param=param, args=args,
                              kwargs=kwargs)

    def _get_param_value(self, param):
        """Get the converted value for an inspect.Parameter."""
        value = getattr(self.namespace, param.name)
        typ = self._get_type(param)

        if isinstance(typ, tuple):
            raise TypeError("{}: Legacy tuple type annotation!".format(
                self.name))

        if hasattr(typing, 'UnionMeta'):
            # Python 3.5.2
            # pylint: disable=no-member,useless-suppression
            is_union = isinstance(
                typ, typing.UnionMeta)  # type: ignore[attr-defined]
        else:
            is_union = getattr(typ, '__origin__', None) is typing.Union

        if is_union:
            # this is... slightly evil, I know
            try:
                types = list(typ.__args__)
            except AttributeError:
                # Python 3.5.2
                types = list(typ.__union_params__)
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

    def _handle_special_call_arg(self, *, pos, param, win_id, args, kwargs):
        """Check whether the argument is special, and if so, fill it in.

        Args:
            pos: The position of the argument.
            param: The argparse.Parameter.
            win_id: The window ID the command is run in.
            args/kwargs: The args/kwargs to fill.

        Return:
            True if it was a special arg, False otherwise.
        """
        arg_info = self.get_arg_info(param)
        if pos == 0 and self._instance is not None:
            assert param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
            self_value = self._get_objreg(win_id=win_id, name=self._instance,
                                          scope=self._scope)
            self._add_special_arg(value=self_value, param=param,
                                  args=args, kwargs=kwargs)
            return True
        elif arg_info.value == usertypes.CommandValue.count:
            if self._count is None:
                assert param.default is not inspect.Parameter.empty
                value = param.default
            else:
                value = self._count
            self._add_special_arg(value=value, param=param,
                                  args=args, kwargs=kwargs)
            return True
        elif arg_info.value == usertypes.CommandValue.win_id:
            self._add_special_arg(value=win_id, param=param,
                                  args=args, kwargs=kwargs)
            return True
        elif arg_info.value == usertypes.CommandValue.cur_tab:
            tab = self._get_objreg(win_id=win_id, name='tab', scope='tab')
            self._add_special_arg(value=tab, param=param,
                                  args=args, kwargs=kwargs)
            return True
        elif arg_info.value == usertypes.CommandValue.count_tab:
            self._add_count_tab(win_id=win_id, param=param, args=args,
                                kwargs=kwargs)
            return True
        elif arg_info.value is None:
            pass
        else:
            raise utils.Unreachable(arg_info)

        return False

    def _get_call_args(self, win_id):
        """Get arguments for a function call.

        Args:
            win_id: The window id this command should be executed in.

        Return:
            An (args, kwargs) tuple.
        """
        args = []  # type: typing.Any
        kwargs = {}  # type: typing.MutableMapping[str, typing.Any]
        signature = inspect.signature(self.handler)

        for i, param in enumerate(signature.parameters.values()):
            if self._handle_special_call_arg(pos=i, param=param,
                                             win_id=win_id, args=args,
                                             kwargs=kwargs):
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
        if mode not in self.modes:
            mode_names = '/'.join(sorted(m.name for m in self.modes))
            raise cmdexc.PrerequisitesError(
                "{}: This command is only allowed in {} mode, not {}.".format(
                    self.name, mode_names, mode.name))

    def takes_count(self):
        """Return true iff this command can take a count argument."""
        return any(info.value in self.COUNT_COMMAND_VALUES
                   for info in self._qute_args.values())

    def register(self):
        """Register this command in objects.commands."""
        log.commands.vdebug(  # type: ignore[attr-defined]
            "Registering command {} (from {}:{})".format(
                self.name, self.handler.__module__, self.handler.__qualname__))
        if self.name in objects.commands:
            raise ValueError("{} is already registered!".format(self.name))
        objects.commands[self.name] = self
