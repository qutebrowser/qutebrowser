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
import collections

from qutebrowser.utils import usertypes, qtutils, log, utils
from qutebrowser.utils import debug as debugutils
from qutebrowser.commands import command, cmdexc, argparser

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
        raise cmdexc.CommandError(
            "Numeric argument is too large for internal {} "
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
        ValueError: If nothing was set.
    """
    if count is not None and arg is not None:
        raise ValueError("Both count and argument given!")
    elif arg is not None:
        return arg
    elif count is not None:
        if countzero is not None and count == 0:
            return countzero
        else:
            return count
    elif default is not None:
        return default
    else:
        raise ValueError("Either count or argument have to be set!")


class register:  # pylint: disable=invalid-name

    """Decorator to register a new command handler.

    This could also be a function, but as a class (with a "wrong" name) it's
    much cleaner to implement.

    Attributes:
        instance: The instance to be used as "self", as a dotted string.
        name: The name (as string) or names (as list) of the command.
        split: Whether to split the arguments.
        hide: Whether to hide the command or not.
        completion: Which completion to use for arguments, as a list of
                    strings.
        modes/not_modes: List of modes to use/not use.
        needs_js: If javascript is needed for this command.
        debug: Whether this is a debugging command (only shown with --debug).
        ignore_args: Whether to ignore the arguments of the function.

    Class attributes:
        AnnotationInfo: Named tuple for info from an annotation.
    """

    AnnotationInfo = collections.namedtuple('AnnotationInfo',
                                            'kwargs, typ, name, flag')

    def __init__(self, instance=None, name=None, split=True, hide=False,
                 completion=None, modes=None, not_modes=None, needs_js=False,
                 debug=False, ignore_args=False):
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
        self.instance = instance
        self.completion = completion
        self.modes = modes
        self.not_modes = not_modes
        self.needs_js = needs_js
        self.debug = debug
        self.ignore_args = ignore_args
        self.parser = None
        self.func = None
        self.docparser = None
        self.opt_args = collections.OrderedDict()
        self.pos_args = []
        if modes is not None:
            for m in modes:
                if not isinstance(m, usertypes.KeyMode):
                    raise TypeError("Mode {} is no KeyMode member!".format(m))
        if not_modes is not None:
            for m in not_modes:
                if not isinstance(m, usertypes.KeyMode):
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
        self.func = func
        names = self._get_names()
        log.commands.vdebug("Registering command {}".format(names[0]))
        for name in names:
            if name in cmd_dict:
                raise ValueError("{} is already registered!".format(name))
        self.docparser = utils.DocstringParser(func)
        self.parser = argparser.ArgumentParser(
            names[0], description=self.docparser.short_desc,
            epilog=self.docparser.long_desc)
        self.parser.add_argument('-h', '--help', action=argparser.HelpAction,
                                 default=argparser.SUPPRESS, nargs=0,
                                 help=argparser.SUPPRESS)
        has_count, desc, type_conv = self._inspect_func()
        cmd = command.Command(
            name=names[0], split=self.split, hide=self.hide, count=has_count,
            desc=desc, instance=self.instance, handler=func,
            completion=self.completion, modes=self.modes,
            not_modes=self.not_modes, needs_js=self.needs_js,
            is_debug=self.debug, parser=self.parser, type_conv=type_conv,
            opt_args=self.opt_args, pos_args=self.pos_args)
        for name in names:
            cmd_dict[name] = cmd
        return func

    def _get_names(self):
        """Get the name(s) which should be used for the current command.

        If the name hasn't been overridden explicitely, the function name is
        transformed.

        If it has been set, it can either be a string which is
        used directly, or an iterable.

        Return:
            A list of names, with the main name being the first item.
        """
        if self.name is None:
            return [self.func.__name__.lower().replace('_', '-')]
        elif isinstance(self.name, str):
            return [self.name]
        else:
            return self.name

    def _inspect_func(self):
        """Inspect the function to get useful informations from it.

        Return:
            A (has_count, desc, parser, type_conv) tuple.
                has_count: Whether the command supports a count.
                desc: The description of the command.
                type_conv: A mapping of args to type converter callables.
        """
        type_conv = {}
        signature = inspect.signature(self.func)
        if 'self' in signature.parameters and self.instance is None:
            raise ValueError("{} is a class method, but instance was not "
                             "given!".format(self.name[0]))
        has_count = 'count' in signature.parameters
        if self.func.__doc__ is not None:
            desc = self.func.__doc__.splitlines()[0].strip()
        else:
            desc = ""
        if not self.ignore_args:
            for param in signature.parameters.values():
                if param.name in ('self', 'count'):
                    continue
                args = []
                kwargs = {}
                annotation_info = self._parse_annotation(param)
                kwargs.update(self._param_to_argparse_kw(
                    param, annotation_info))
                kwargs.update(annotation_info.kwargs)
                args += self._param_to_argparse_pos(param, annotation_info)
                typ = self._get_type(param, annotation_info)
                if utils.is_enum(typ):
                    type_conv[param.name] = argparser.enum_getter(typ)
                elif isinstance(typ, tuple):
                    if param.default is not inspect.Parameter.empty:
                        typ = typ + (type(param.default),)
                    type_conv[param.name] = argparser.multitype_conv(typ)
                callsig = debugutils.format_call(self.parser.add_argument,
                                                 args, kwargs, full=False)
                log.commands.vdebug('Adding arg {} of type {} -> {}'.format(
                    param.name, typ, callsig))
                self.parser.add_argument(*args, **kwargs)
        return has_count, desc, type_conv

    def _param_to_argparse_pos(self, param, annotation_info):
        """Get a list of positional argparse arguments.

        Args:
            param: The inspect.Parameter instance for the current parameter.
            annotation_info: An AnnotationInfo tuple for the parameter.
        """
        args = []
        name = annotation_info.name or param.name
        shortname = annotation_info.flag or param.name[0]
        if self._get_type(param, annotation_info) == bool:
            long_flag = '--{}'.format(name)
            short_flag = '-{}'.format(shortname)
            args.append(long_flag)
            args.append(short_flag)
            self.opt_args[name] = long_flag, short_flag
        else:
            args.append(name)
            self.pos_args.append(name)
        return args

    def _param_to_argparse_kw(self, param, annotation_info):
        """Get argparse keyword arguments for a parameter.

        Args:
            param: The inspect.Parameter object to get the args for.
            annotation_info: An AnnotationInfo tuple for the parameter.
        """
        kwargs = {}

        try:
            kwargs['help'] = self.docparser.arg_descs[param.name]
        except KeyError:
            pass
        typ = self._get_type(param, annotation_info)

        if isinstance(typ, tuple):
            pass
        elif utils.is_enum(typ):
            kwargs['choices'] = [e.name.replace('_', '-') for e in typ]
            kwargs['metavar'] = param.name
        elif typ is bool:
            kwargs['action'] = 'store_true'
        elif typ is not None:
            kwargs['type'] = typ

        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            kwargs['nargs'] = '*'
        elif typ is not bool and param.default is not inspect.Parameter.empty:
            kwargs['default'] = param.default
            kwargs['nargs'] = '?'

        return kwargs

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
