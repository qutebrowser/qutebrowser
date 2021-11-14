# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Utilities used for debugging."""

import re
import inspect
import logging
import functools
import datetime
import types
from typing import (
    Any, Callable, List, Mapping, MutableSequence, Optional, Sequence, Type, Union)

from PyQt5.QtCore import Qt, QEvent, QMetaMethod, QObject, pyqtBoundSignal

from qutebrowser.utils import log, utils, qtutils, objreg
from qutebrowser.misc import objects
from qutebrowser.qt import sip


def log_events(klass: Type[QObject]) -> Type[QObject]:
    """Class decorator to log Qt events."""
    old_event = klass.event

    @functools.wraps(old_event)
    def new_event(self: Any, e: QEvent) -> bool:
        """Wrapper for event() which logs events."""
        log.misc.debug("Event in {}: {}".format(utils.qualname(klass),
                                                qenum_key(QEvent, e.type())))
        return old_event(self, e)

    klass.event = new_event  # type: ignore[assignment]
    return klass


def log_signals(obj: QObject) -> QObject:
    """Log all signals of an object or class.

    Can be used as class decorator.
    """
    def log_slot(obj: QObject, signal: pyqtBoundSignal, *args: Any) -> None:
        """Slot connected to a signal to log it."""
        dbg = dbg_signal(signal, args)
        try:
            r = repr(obj)
        except RuntimeError:  # pragma: no cover
            r = '<deleted>'
        log.signals.debug("Signal in {}: {}".format(r, dbg))

    def connect_log_slot(obj: QObject) -> None:
        """Helper function to connect all signals to a logging slot."""
        metaobj = obj.metaObject()
        for i in range(metaobj.methodCount()):
            meta_method = metaobj.method(i)
            qtutils.ensure_valid(meta_method)
            if meta_method.methodType() == QMetaMethod.Signal:
                name = meta_method.name().data().decode('ascii')
                if name != 'destroyed':
                    signal = getattr(obj, name)
                    try:
                        signal.connect(functools.partial(
                            log_slot, obj, signal))
                    except TypeError:  # pragma: no cover
                        pass

    if inspect.isclass(obj):
        old_init = obj.__init__  # type: ignore[misc]

        @functools.wraps(old_init)
        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            """Wrapper for __init__() which logs signals."""
            old_init(self, *args, **kwargs)
            connect_log_slot(self)

        obj.__init__ = new_init  # type: ignore[misc]
    else:
        connect_log_slot(obj)

    return obj


_EnumValueType = Union[sip.simplewrapper, int]


def qenum_key(base: Type[_EnumValueType],
              value: _EnumValueType,
              add_base: bool = False,
              klass: Type[_EnumValueType] = None) -> str:
    """Convert a Qt Enum value to its key as a string.

    Args:
        base: The object the enum is in, e.g. QFrame.
        value: The value to get.
        add_base: Whether the base should be added to the printed name.
        klass: The enum class the value belongs to.
               If None, the class will be auto-guessed.

    Return:
        The key associated with the value as a string if it could be found.
        The original value as a string if not.
    """
    if klass is None:
        klass = value.__class__
        if klass == int:
            raise TypeError("Can't guess enum class of an int!")

    try:
        meta_obj = base.staticMetaObject  # type: ignore[union-attr]
        idx = meta_obj.indexOfEnumerator(klass.__name__)
        meta_enum = meta_obj.enumerator(idx)
        ret = meta_enum.valueToKey(int(value))  # type: ignore[arg-type]
    except AttributeError:
        ret = None

    if ret is None:
        for name, obj in vars(base).items():
            if isinstance(obj, klass) and obj == value:
                ret = name
                break
        else:
            ret = '0x{:04x}'.format(int(value))  # type: ignore[arg-type]

    if add_base and hasattr(base, '__name__'):
        return '.'.join([base.__name__, ret])
    else:
        return ret


def qflags_key(base: Type[_EnumValueType],
               value: _EnumValueType,
               add_base: bool = False,
               klass: Type[_EnumValueType] = None) -> str:
    """Convert a Qt QFlags value to its keys as string.

    Note: Passing a combined value (such as Qt.AlignCenter) will get the names
    for the individual bits (e.g. Qt.AlignVCenter | Qt.AlignHCenter). FIXME

    https://github.com/qutebrowser/qutebrowser/issues/42

    Args:
        base: The object the flags are in, e.g. QtCore.Qt
        value: The value to get.
        add_base: Whether the base should be added to the printed names.
        klass: The flags class the value belongs to.
               If None, the class will be auto-guessed.

    Return:
        The keys associated with the flags as a '|' separated string if they
        could be found. Hex values as a string if not.
    """
    if klass is None:
        # We have to store klass here because it will be lost when iterating
        # over the bits.
        klass = value.__class__
        if klass == int:
            raise TypeError("Can't guess enum class of an int!")

    if not value:
        return qenum_key(base, value, add_base, klass)

    bits = []
    names = []
    mask = 0x01
    value = int(value)  # type: ignore[arg-type]
    while mask <= value:
        if value & mask:
            bits.append(mask)
        mask <<= 1
    for bit in bits:
        # We have to re-convert to an enum type here or we'll sometimes get an
        # empty string back.
        enum_value = klass(bit)  # type: ignore[call-arg]
        names.append(qenum_key(base, enum_value, add_base))
    return '|'.join(names)


def signal_name(sig: pyqtBoundSignal) -> str:
    """Get a cleaned up name of a signal.

    Unfortunately, the way to get the name of a signal differs based on
    bound vs. unbound signals.

    Here, we try to get the name from .signal or .signatures, or if all else
    fails, extract it from the repr().

    Args:
        sig: A bound signal.

    Return:
        The cleaned up signal name.
    """
    if hasattr(sig, 'signal'):
        # Bound signal
        # Examples:
        # sig.signal == '2signal1'
        # sig.signal == '2signal2(QString,QString)'
        m = re.fullmatch(r'[0-9]+(?P<name>.*)\(.*\)', sig.signal)
    else:
        # Unbound signal, PyQt >= 5.11
        # Examples:
        # sig.signatures == ('signal1()',)
        # sig.signatures == ('signal2(QString,QString)',)
        m = re.fullmatch(r'(?P<name>.*)\(.*\)',
                         sig.signatures[0])  # type: ignore[attr-defined]

    assert m is not None, sig
    return m.group('name')


def format_args(args: Sequence[Any] = None, kwargs: Mapping[str, Any] = None) -> str:
    """Format a list of arguments/kwargs to a function-call like string."""
    if args is not None:
        arglist = [utils.compact_text(repr(arg), 200) for arg in args]
    else:
        arglist = []
    if kwargs is not None:
        for k, v in kwargs.items():
            arglist.append('{}={}'.format(k, utils.compact_text(repr(v), 200)))
    return ', '.join(arglist)


def dbg_signal(sig: pyqtBoundSignal, args: Any) -> str:
    """Get a string representation of a signal for debugging.

    Args:
        sig: A bound signal.
        args: The arguments as list of strings.

    Return:
        A human-readable string representation of signal/args.
    """
    return '{}({})'.format(signal_name(sig), format_args(args))


def format_call(func: Callable[..., Any],
                args: Sequence[Any] = None,
                kwargs: Mapping[str, Any] = None,
                full: bool = True) -> str:
    """Get a string representation of a function calls with the given args.

    Args:
        func: The callable to print.
        args: A list of positional arguments.
        kwargs: A dict of named arguments.
        full: Whether to print the full name

    Return:
        A string with the function call.
    """
    if full:
        name = utils.qualname(func)
    else:
        name = func.__name__
    return '{}({})'.format(name, format_args(args, kwargs))


class log_time:  # noqa: N801,N806 pylint: disable=invalid-name

    """Log the time an operation takes.

    Usable as context manager or as decorator.
    """

    def __init__(self, logger: Union[logging.Logger, str],
                 action: str = 'operation') -> None:
        """Constructor.

        Args:
            logger: The logging.Logger to use for logging, or a logger name.
            action: A description of what's being done.
        """
        if isinstance(logger, str):
            self._logger = logging.getLogger(logger)
        else:
            self._logger = logger
        self._started: Optional[datetime.datetime] = None
        self._action = action

    def __enter__(self) -> None:
        self._started = datetime.datetime.now()

    def __exit__(self,
                 _exc_type: Optional[Type[BaseException]],
                 _exc_val: Optional[BaseException],
                 _exc_tb: Optional[types.TracebackType]) -> None:
        assert self._started is not None
        finished = datetime.datetime.now()
        delta = (finished - self._started).total_seconds()
        self._logger.debug("{} took {} seconds.".format(
            self._action.capitalize(), delta))

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            """Call the original function."""
            with self:
                return func(*args, **kwargs)

        return wrapped


def _get_widgets() -> Sequence[str]:
    """Get a string list of all widgets."""
    widgets = objects.qapp.allWidgets()
    widgets.sort(key=repr)
    return [repr(w) for w in widgets]


def _get_pyqt_objects(lines: MutableSequence[str],
                      obj: QObject,
                      depth: int = 0) -> None:
    """Recursive method for get_all_objects to get Qt objects."""
    for kid in obj.findChildren(QObject, '', Qt.FindDirectChildrenOnly):
        lines.append('    ' * depth + repr(kid))
        _get_pyqt_objects(lines, kid, depth + 1)


def get_all_objects(start_obj: QObject = None) -> str:
    """Get all children of an object recursively as a string."""
    output = ['']
    widget_lines = _get_widgets()
    widget_lines = ['    ' + e for e in widget_lines]
    widget_lines.insert(0, "Qt widgets - {} objects:".format(
        len(widget_lines)))
    output += widget_lines

    if start_obj is None:
        start_obj = objects.qapp

    pyqt_lines: List[str] = []
    _get_pyqt_objects(pyqt_lines, start_obj)
    pyqt_lines = ['    ' + e for e in pyqt_lines]
    pyqt_lines.insert(0, 'Qt objects - {} objects:'.format(len(pyqt_lines)))

    output += ['']
    output += pyqt_lines
    output += objreg.dump_objects()
    return '\n'.join(output)
