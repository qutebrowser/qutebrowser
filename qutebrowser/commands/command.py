# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtWebKit import QWebSettings

from qutebrowser.commands import cmdexc, argparser
from qutebrowser.utils import log, utils, message, docutils, objreg, usertypes
from qutebrowser.utils import debug as debug_utils


def arg_name(name):
    """Get the name an argument should have based on its Python name."""
    return name.rstrip('_').replace('_', '-')


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
        completion: Completions to use for arguments, as a list of strings.
        debug: Whether this is a debugging command (only shown with --debug).
        parser: The ArgumentParser to use to parse this command.
        count_arg: The name of the count parameter, or None.
        win_id_arg: The name of the win_id parameter, or None.
        flags_with_args: A list of flags which take an argument.
        no_cmd_split: If true, ';;' to split sub-commands is ignored.
        _type_conv: A mapping of conversion functions for arguments.
        _needs_js: Whether the command needs javascript enabled
        _modes: The modes the command can be executed in.
        _not_modes: The modes the command can not be executed in.
        _count: The count set for the command.
        _instance: The object to bind 'self' to.
        _scope: The scope to get _instance for in the object registry.

    Class attributes:
        AnnotationInfo: Named tuple for info from an annotation.
    """

    AnnotationInfo = collections.namedtuple('AnnotationInfo',
                                            ['kwargs', 'type', 'flag', 'hide',
                                             'metavar'])

    def __init__(self, *, handler, name, instance=None, maxsplit=None,
                 hide=False, completion=None, modes=None, not_modes=None,
                 needs_js=False, debug=False, ignore_args=False,
                 deprecated=False, no_cmd_split=False, scope='global',
                 count=None, win_id=None):
        # I really don't know how to solve this in a better way, I tried.
        # pylint: disable=too-many-arguments,too-many-locals
        if modes is not None and not_modes is not None:
            raise ValueError("Only modes or not_modes can be given!")
        if modes is not None:
            for m in modes:
                if not isinstance(m, usertypes.KeyMode):
                    raise TypeError("Mode {} is no KeyMode member!".format(m))
        if not_modes is not None:
            for m in not_modes:
                if not isinstance(m, usertypes.KeyMode):
                    raise TypeError("Mode {} is no KeyMode member!".format(m))
        if scope != 'global' and instance is None:
            raise ValueError("Setting scope without setting instance makes "
                             "no sense!")
        self.name = name
        self.maxsplit = maxsplit
        self.hide = hide
        self.deprecated = deprecated
        self._instance = instance
        self.completion = completion
        self._modes = modes
        self._not_modes = not_modes
        self._scope = scope
        self._needs_js = needs_js
        self.debug = debug
        self.ignore_args = ignore_args
        self.handler = handler
        self.no_cmd_split = no_cmd_split
        self.count_arg = count
        self.win_id_arg = win_id
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
        self._type_conv = {}
        count = self._inspect_func()
        if self.completion is not None and len(self.completion) > count:
            raise ValueError("Got {} completions, but only {} "
                             "arguments!".format(len(self.completion), count))

    def _check_prerequisites(self, win_id):
        """Check if the command is permitted to run currently.

        Args:
            win_id: The window ID the command is run in.
        """
        mode_manager = objreg.get('mode-manager', scope='window',
                                  window=win_id)
        curmode = mode_manager.mode
        if self._modes is not None and curmode not in self._modes:
            mode_names = '/'.join(mode.name for mode in self._modes)
            raise cmdexc.PrerequisitesError(
                "{}: This command is only allowed in {} mode.".format(
                    self.name, mode_names))
        elif self._not_modes is not None and curmode in self._not_modes:
            mode_names = '/'.join(mode.name for mode in self._not_modes)
            raise cmdexc.PrerequisitesError(
                "{}: This command is not allowed in {} mode.".format(
                    self.name, mode_names))
        if self._needs_js and not QWebSettings.globalSettings().testAttribute(
                QWebSettings.JavascriptEnabled):
            raise cmdexc.PrerequisitesError(
                "{}: This command needs javascript enabled.".format(self.name))
        if self.deprecated:
            message.warning(win_id, '{} is deprecated - {}'.format(
                self.name, self.deprecated))

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

    def _get_typeconv(self, param, typ):
        """Get a dict with a type conversion for the parameter.

        Args:
            param: The inspect.Parameter to handle.
            typ: The type of the parameter.
        """
        type_conv = {}
        if utils.is_enum(typ):
            type_conv[param.name] = argparser.enum_getter(typ)
        elif isinstance(typ, tuple):
            if param.default is not inspect.Parameter.empty:
                typ = typ + (type(param.default),)
            type_conv[param.name] = argparser.multitype_conv(typ)
        return type_conv

    def _inspect_special_param(self, param):
        """Check if the given parameter is a special one.

        Args:
            param: The inspect.Parameter to handle.

        Return:
            True if the parameter is special, False otherwise.
        """
        if param.name == self.count_arg:
            if param.default is inspect.Parameter.empty:
                raise TypeError("{}: handler has count parameter "
                                "without default!".format(self.name))
            return True
        elif param.name == self.win_id_arg:
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
        arg_count = 0
        if doc is not None:
            self.desc = doc.splitlines()[0].strip()
        else:
            self.desc = ""

        if (self.count_arg is not None and
                self.count_arg not in signature.parameters):
            raise ValueError("count parameter {} does not exist!".format(
                self.count_arg))
        if (self.win_id_arg is not None and
                self.win_id_arg not in signature.parameters):
            raise ValueError("win_id parameter {} does not exist!".format(
                self.win_id_arg))

        if not self.ignore_args:
            for param in signature.parameters.values():
                annotation_info = self._parse_annotation(param)
                if param.name == 'self':
                    continue
                if self._inspect_special_param(param):
                    continue
                arg_count += 1
                typ = self._get_type(param, annotation_info)
                kwargs = self._param_to_argparse_kwargs(param, annotation_info)
                args = self._param_to_argparse_args(param, annotation_info)
                self._type_conv.update(self._get_typeconv(param, typ))
                callsig = debug_utils.format_call(
                    self.parser.add_argument, args, kwargs,
                    full=False)
                log.commands.vdebug('Adding arg {} of type {} -> {}'.format(
                    param.name, typ, callsig))
                self.parser.add_argument(*args, **kwargs)
        return arg_count

    def _param_to_argparse_kwargs(self, param, annotation_info):
        """Get argparse keyword arguments for a parameter.

        Args:
            param: The inspect.Parameter object to get the args for.
            annotation_info: An AnnotationInfo tuple for the parameter.

        Return:
            A kwargs dict.
        """
        kwargs = {}
        typ = self._get_type(param, annotation_info)

        try:
            kwargs['help'] = self.docparser.arg_descs[param.name]
        except KeyError:
            pass

        kwargs['dest'] = param.name

        if isinstance(typ, tuple):
            kwargs['metavar'] = annotation_info.metavar or param.name
        elif utils.is_enum(typ):
            kwargs['choices'] = [arg_name(e.name) for e in typ]
            kwargs['metavar'] = annotation_info.metavar or param.name
        elif typ is bool:
            kwargs['action'] = 'store_true'
        elif typ is not None:
            kwargs['type'] = typ

        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            kwargs['nargs'] = '+'
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            kwargs['default'] = param.default
        elif typ is not bool and param.default is not inspect.Parameter.empty:
            kwargs['default'] = param.default
            kwargs['nargs'] = '?'
        kwargs.update(annotation_info.kwargs)
        return kwargs

    def _param_to_argparse_args(self, param, annotation_info):
        """Get argparse positional arguments for a parameter.

        Args:
            param: The inspect.Parameter object to get the args for.
            annotation_info: An AnnotationInfo tuple for the parameter.

        Return:
            A list of args.
        """
        args = []
        name = arg_name(param.name)
        shortname = annotation_info.flag or name[0]
        if len(shortname) != 1:
            raise ValueError("Flag '{}' of parameter {} (command {}) must be "
                             "exactly 1 char!".format(shortname, name,
                                                      self.name))
        typ = self._get_type(param, annotation_info)
        if typ is bool or param.kind == inspect.Parameter.KEYWORD_ONLY:
            long_flag = '--{}'.format(name)
            short_flag = '-{}'.format(shortname)
            args.append(long_flag)
            args.append(short_flag)
            self.opt_args[param.name] = long_flag, short_flag
            if typ is not bool:
                self.flags_with_args += [short_flag, long_flag]
        else:
            if not annotation_info.hide:
                self.pos_args.append((param.name, name))
        return args

    def _parse_annotation(self, param):
        """Get argparse arguments and type from a parameter annotation.

        Args:
            param: A inspect.Parameter instance.

        Return:
            An AnnotationInfo namedtuple.
                kwargs: A dict of keyword args to add to the
                        argparse.ArgumentParser.add_argument call.
                typ: The type to use for this argument.
                flag: The short name/flag if overridden.
                name: The long name if overridden.
        """
        info = {'kwargs': {}, 'type': None, 'flag': None, 'hide': False,
                'metavar': None}
        if param.annotation is not inspect.Parameter.empty:
            log.commands.vdebug("Parsing annotation {}".format(
                param.annotation))
            for field in ('type', 'flag', 'name', 'hide', 'metavar'):
                if field in param.annotation:
                    info[field] = param.annotation[field]
            if 'nargs' in param.annotation:
                info['kwargs'] = {'nargs': param.annotation['nargs']}
        return self.AnnotationInfo(**info)

    def _get_type(self, param, annotation_info):
        """Get the type of an argument from its default value or annotation.

        Args:
            param: The inspect.Parameter to look at.
            annotation_info: An AnnotationInfo tuple which overrides the type.
        """
        if annotation_info.type is not None:
            return annotation_info.type
        elif param.default is None or param.default is inspect.Parameter.empty:
            return None
        else:
            return type(param.default)

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
        if param.name in self._type_conv:
            # We convert enum types after getting the values from
            # argparse, because argparse's choices argument is
            # processed after type conversation, which is not what we
            # want.
            value = self._type_conv[param.name](value)
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
            if i == 0 and self._instance is not None:
                # Special case for 'self'.
                self._get_self_arg(win_id, param, args)
                continue
            elif param.name == self.count_arg:
                # Special case for count parameter.
                self._get_count_arg(param, args, kwargs)
                continue
            elif param.name == self.win_id_arg:
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
        if count is not None:
            dbgout.append("(count={})".format(count))
        log.commands.debug(' '.join(dbgout))
        try:
            self.namespace = self.parser.parse_args(args)
        except argparser.ArgumentParserError as e:
            message.error(win_id, '{}: {}'.format(self.name, e))
            return
        except argparser.ArgumentParserExit as e:
            log.commands.debug("argparser exited with status {}: {}".format(
                e.status, e))
            return
        self._count = count
        posargs, kwargs = self._get_call_args(win_id)
        self._check_prerequisites(win_id)
        log.commands.debug('Calling {}'.format(
            debug_utils.format_call(self.handler, posargs, kwargs)))
        self.handler(*posargs, **kwargs)
