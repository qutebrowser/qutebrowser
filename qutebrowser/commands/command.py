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
import collections

from PyQt5.QtWebKit import QWebSettings

from qutebrowser.commands import cmdexc, argparser
from qutebrowser.utils import (log, utils, message, debug, usertypes, docutils,
                               objreg)


class Command:

    """Base skeleton for a command.

    Attributes:
        name: The main name of the command.
        split: Whether to split the arguments.
        hide: Whether to hide the arguments or not.
        desc: The description of the command.
        handler: The handler function to call.
        completion: Completions to use for arguments, as a list of strings.
        debug: Whether this is a debugging command (only shown with --debug).
        parser: The ArgumentParser to use to parse this command.
        _type_conv: A mapping of conversion functions for arguments.
        _name_conv: A mapping of argument names to parameter names.
        _needs_js: Whether the command needs javascript enabled
        _modes: The modes the command can be executed in.
        _not_modes: The modes the command can not be executed in.
        _count: Whether the command supports a count, or not.
        _instance: The object to bind 'self' to.

    Class attributes:
        AnnotationInfo: Named tuple for info from an annotation.
        ParamType: Enum for an argparse parameter type.
    """

    AnnotationInfo = collections.namedtuple('AnnotationInfo',
                                            'kwargs, typ, name, flag')
    ParamType = usertypes.enum('ParamType', 'flag', 'positional')

    def __init__(self, name, split, hide, instance, completion, modes,
                 not_modes, needs_js, is_debug, ignore_args,
                 handler):
        # I really don't know how to solve this in a better way, I tried.
        # pylint: disable=too-many-arguments,too-many-locals
        self.name = name
        self.split = split
        self.hide = hide
        self._instance = instance
        self.completion = completion
        self._modes = modes
        self._not_modes = not_modes
        self._needs_js = needs_js
        self.debug = is_debug
        self.ignore_args = ignore_args
        self.handler = handler
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
        has_count, desc, type_conv, name_conv = self._inspect_func()
        self.has_count = has_count
        self.desc = desc
        self._type_conv = type_conv
        self._name_conv = name_conv

    def _check_prerequisites(self):
        """Check if the command is permitted to run currently.

        Raise:
            PrerequisitesError if the command can't be called currently.
        """
        curmode = objreg.get('mode-manager').mode()
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

    def _check_func(self):
        """Make sure the function parameters don't violate any rules."""
        signature = inspect.signature(self.handler)
        if 'self' in signature.parameters and self._instance is None:
            raise TypeError("{} is a class method, but instance was not "
                            "given!".format(self.name[0]))
        elif 'self' not in signature.parameters and self._instance is not None:
            raise TypeError("{} is not a class method, but instance was "
                            "given!".format(self.name[0]))
        elif inspect.getfullargspec(self.handler).varkw is not None:
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

    def _get_nameconv(self, param, annotation_info):
        """Get a dict with a name conversion for the paraeter.

        Args:
            param: The inspect.Parameter to handle.
            annotation_info: The AnnotationInfo tuple for the parameter.
        """
        d = {}
        if annotation_info.name is not None:
            d[param.name] = annotation_info.name
        return d

    def _inspect_func(self):
        """Inspect the function to get useful informations from it.

        Return:
            A (has_count, desc, parser, type_conv) tuple.
                has_count: Whether the command supports a count.
                desc: The description of the command.
                type_conv: A mapping of args to type converter callables.
                name_conv: A mapping of names to convert.
        """
        type_conv = {}
        name_conv = {}
        signature = inspect.signature(self.handler)
        has_count = 'count' in signature.parameters
        doc = inspect.getdoc(self.handler)
        if doc is not None:
            desc = doc.splitlines()[0].strip()
        else:
            desc = ""
        if not self.ignore_args:
            for param in signature.parameters.values():
                if param.name in ('self', 'count'):
                    continue
                annotation_info = self._parse_annotation(param)
                typ = self._get_type(param, annotation_info)
                args, kwargs = self._param_to_argparse_args(
                    param, annotation_info)
                type_conv.update(self._get_typeconv(param, typ))
                name_conv.update(self._get_nameconv(param, annotation_info))
                callsig = debug.format_call(
                    self.parser.add_argument, args, kwargs,
                    full=False)
                log.commands.vdebug('Adding arg {} of type {} -> {}'.format(
                    param.name, typ, callsig))
                self.parser.add_argument(*args, **kwargs)
        return has_count, desc, type_conv, name_conv

    def _param_to_argparse_args(self, param, annotation_info):
        """Get argparse arguments for a parameter.

        Return:
            An (args, kwargs) tuple.

        Args:
            param: The inspect.Parameter object to get the args for.
            annotation_info: An AnnotationInfo tuple for the parameter.
        """

        kwargs = {}
        typ = self._get_type(param, annotation_info)
        param_type = self.ParamType.positional

        try:
            kwargs['help'] = self.docparser.arg_descs[param.name]
        except KeyError:
            pass

        if isinstance(typ, tuple):
            pass
        elif utils.is_enum(typ):
            kwargs['choices'] = [e.name.replace('_', '-') for e in typ]
            kwargs['metavar'] = param.name
        elif typ is bool:
            param_type = self.ParamType.flag
            kwargs['action'] = 'store_true'
        elif typ is not None:
            kwargs['type'] = typ

        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            kwargs['nargs'] = '+'
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            param_type = self.ParamType.flag
            kwargs['default'] = param.default
        elif typ is not bool and param.default is not inspect.Parameter.empty:
            kwargs['default'] = param.default
            kwargs['nargs'] = '?'

        args = []
        name = annotation_info.name or param.name
        shortname = annotation_info.flag or param.name[0]
        if param_type == self.ParamType.flag:
            long_flag = '--{}'.format(name)
            short_flag = '-{}'.format(shortname)
            args.append(long_flag)
            args.append(short_flag)
            self.opt_args[param.name] = long_flag, short_flag
        elif param_type == self.ParamType.positional:
            args.append(name)
            self.pos_args.append((param.name, name))
        else:
            raise ValueError("Invalid ParamType {}!".format(param_type))
        kwargs.update(annotation_info.kwargs)
        return args, kwargs

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
        info = {'kwargs': {}, 'typ': None, 'flag': None, 'name': None}
        if param.annotation is not inspect.Parameter.empty:
            log.commands.vdebug("Parsing annotation {}".format(
                param.annotation))
            if isinstance(param.annotation, dict):
                for field in ('type', 'flag', 'name'):
                    if field in param.annotation:
                        info[field] = param.annotation[field]
                        del param.annotation[field]
                info['kwargs'] = param.annotation
            else:
                info['typ'] = param.annotation
        return self.AnnotationInfo(**info)

    def _get_type(self, param, annotation_info):
        """Get the type of an argument from its default value or annotation.

        Args:
            param: The inspect.Parameter to look at.
            annotation_info: An AnnotationInfo tuple which overrides the type.
        """
        if annotation_info.typ is not None:
            return annotation_info.typ
        elif param.default is None or param.default is inspect.Parameter.empty:
            return None
        else:
            return type(param.default)

    def _get_self_arg(self, param, args):
        """Get the self argument for a function call.

        Arguments:
            param: The count parameter.
            args: The positional argument list. Gets modified directly.
        """
        assert param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        obj = objreg.get(self._instance)
        args.append(obj)

    def _get_count_arg(self, param, args, kwargs):
        """Add the count argument to a function call.

        Arguments:
            param: The count parameter.
            args: The positional argument list. Gets modified directly.
            kwargs: The keyword argument dict. Gets modified directly.
        """
        if not self.has_count:
            raise TypeError("{}: count argument given with a command which "
                            "does not support count!".format(self.name))
        if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            if self._count is not None:
                args.append(self._count)
            else:
                args.append(param.default)
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            if self._count is not None:
                kwargs['count'] = self._count
        else:
            raise TypeError("{}: invalid parameter type {} for argument "
                            "'count'!".format(self.name, param.kind))

    def _get_param_name_and_value(self, param):
        """Get the converted name and value for an inspect.Parameter."""
        name = self._name_conv.get(param.name, param.name)
        value = getattr(self.namespace, name)
        if param.name in self._type_conv:
            # We convert enum types after getting the values from
            # argparse, because argparse's choices argument is
            # processed after type conversation, which is not what we
            # want.
            value = self._type_conv[param.name](value)
        return name, value

    def _get_call_args(self):
        """Get arguments for a function call.

        Return:
            An (args, kwargs) tuple.
        """

        args = []
        kwargs = {}
        signature = inspect.signature(self.handler)

        if self.ignore_args:
            if self._instance is not None:
                param = list(signature.parameters.values())[0]
                self._get_self_arg(param, args)
            return args, kwargs

        for i, param in enumerate(signature.parameters.values()):
            if i == 0 and self._instance is not None:
                # Special case for 'self'.
                self._get_self_arg(param, args)
                continue
            elif param.name == 'count':
                # Special case for 'count'.
                self._get_count_arg(param, args, kwargs)
                continue
            name, value = self._get_param_name_and_value(param)
            if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                args.append(value)
            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                if value is not None:
                    args += value
            elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                kwargs[name] = value
            else:
                raise TypeError("{}: Invalid parameter type {} for argument "
                                "'{}'!".format(
                                    self.name, param.kind, param.name))
        return args, kwargs

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
        try:
            self.namespace = self.parser.parse_args(args)
        except argparser.ArgumentParserError as e:
            message.error('{}: {}'.format(self.name, e))
            return
        except argparser.ArgumentParserExit as e:
            log.commands.debug("argparser exited with status {}: {}".format(
                e.status, e))
            return
        self._count = count
        posargs, kwargs = self._get_call_args()
        self._check_prerequisites()
        log.commands.debug('Calling {}'.format(
            debug.format_call(self.handler, posargs, kwargs)))
        self.handler(*posargs, **kwargs)
