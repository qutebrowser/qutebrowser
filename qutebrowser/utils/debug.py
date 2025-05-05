# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utilities used for debugging."""

import re
import enum
import inspect
import logging
import functools
import datetime
import types
from typing import (
    Any, Optional, Union)
from collections.abc import Mapping, MutableSequence, Sequence, Callable

from qutebrowser.qt.core import Qt, QEvent, QMetaMethod, QObject, pyqtBoundSignal
from qutebrowser.qt.widgets import QApplication

from qutebrowser.utils import log, utils, qtutils, objreg
from qutebrowser.misc import objects
from qutebrowser.qt import sip, machinery


def log_events(klass: type[QObject]) -> type[QObject]:
    """Class decorator to log Qt events."""
    old_event = klass.event

    @functools.wraps(old_event)
    def new_event(self: Any, e: QEvent) -> bool:
        """Wrapper for event() which logs events."""
        # Passing klass as a WORKAROUND because with PyQt6, QEvent.type() returns int:
        # https://www.riverbankcomputing.com/pipermail/pyqt/2022-April/044583.html
        log.misc.debug("Event in {}: {}".format(
            utils.qualname(klass), qenum_key(QEvent, e.type(), klass=QEvent.Type)))
        return old_event(self, e)

    klass.event = new_event  # type: ignore[assignment]
    return klass


def log_signals(obj: Union[QObject, type[QObject]]) -> Union[QObject, type[QObject]]:
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
        assert metaobj is not None
        for i in range(metaobj.methodCount()):
            meta_method = metaobj.method(i)
            qtutils.ensure_valid(meta_method)
            if meta_method.methodType() == QMetaMethod.MethodType.Signal:
                name = meta_method.name().data().decode('ascii')
                if name != 'destroyed':
                    signal = getattr(obj, name)
                    try:
                        signal.connect(functools.partial(
                            log_slot, obj, signal))
                    except TypeError:  # pragma: no cover
                        pass

    if inspect.isclass(obj):
        old_init = obj.__init__

        @functools.wraps(old_init)
        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            """Wrapper for __init__() which logs signals."""
            old_init(self, *args, **kwargs)
            connect_log_slot(self)

        obj.__init__ = new_init
    else:
        assert isinstance(obj, QObject)
        connect_log_slot(obj)

    return obj


if machinery.IS_QT6:
    _EnumValueType = Union[enum.Enum, int]
else:
    _EnumValueType = Union[sip.simplewrapper, int]


def _qenum_key_python(
    value: _EnumValueType,
    klass: type[_EnumValueType],
) -> Optional[str]:
    """New-style PyQt6: Try getting value from Python enum."""
    if isinstance(value, enum.Enum) and value.name:
        return value.name

    # We got an int with klass passed: Try asking Python enum for member
    if issubclass(klass, enum.Enum):
        try:
            assert isinstance(value, int)
            name = klass(value).name
            if name is not None and name != str(value):
                return name
        except ValueError:
            pass

    return None


def _qenum_key_qt(
    base: type[sip.simplewrapper],
    value: _EnumValueType,
    klass: type[_EnumValueType],
) -> Optional[str]:
    # On PyQt5, or PyQt6 with int passed: Try to ask Qt's introspection.
    # However, not every Qt enum value has a staticMetaObject
    try:
        meta_obj = base.staticMetaObject  # type: ignore[attr-defined]
        idx = meta_obj.indexOfEnumerator(klass.__name__)
        meta_enum = meta_obj.enumerator(idx)
        key = meta_enum.valueToKey(int(value))  # type: ignore[arg-type]
        if key is not None:
            return key
    except AttributeError:
        pass

    # PyQt5: Try finding value match in class
    for name, obj in vars(base).items():
        if isinstance(obj, klass) and obj == value:
            return name

    return None


def qenum_key(
    base: type[sip.simplewrapper],
    value: _EnumValueType,
    klass: type[_EnumValueType] = None,
) -> str:
    """Convert a Qt Enum value to its key as a string.

    Args:
        base: The object the enum is in, e.g. QFrame.
        value: The value to get.
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
    assert klass is not None

    name = _qenum_key_python(value=value, klass=klass)
    if name is not None:
        return name

    name = _qenum_key_qt(base=base, value=value, klass=klass)
    if name is not None:
        return name

    # Last resort fallback: Hex value
    return '0x{:04x}'.format(int(value))  # type: ignore[arg-type]


def qflags_key(base: type[sip.simplewrapper],
               value: _EnumValueType,
               klass: type[_EnumValueType] = None) -> str:
    """Convert a Qt QFlags value to its keys as string.

    Note: Passing a combined value (such as Qt.AlignmentFlag.AlignCenter) will get the names
    for the individual bits (e.g. Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter). FIXME

    https://github.com/qutebrowser/qutebrowser/issues/42

    Args:
        base: The object the flags are in, e.g. QtCore.Qt
        value: The value to get.
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
        return qenum_key(base, value, klass)

    bits = []
    names = []
    mask = 0x01
    intval = qtutils.extract_enum_val(value)
    while mask <= intval:
        if intval & mask:
            bits.append(mask)
        mask <<= 1
    for bit in bits:
        # We have to re-convert to an enum type here or we'll sometimes get an
        # empty string back.
        enum_value = klass(bit)  # type: ignore[call-arg,unused-ignore]
        names.append(qenum_key(base, enum_value, klass))
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
                 _exc_type: Optional[type[BaseException]],
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


def _get_widgets(qapp: QApplication) -> Sequence[str]:
    """Get a string list of all widgets."""
    widgets = qapp.allWidgets()
    widgets.sort(key=repr)
    return [repr(w) for w in widgets]


def _get_pyqt_objects(lines: MutableSequence[str],
                      obj: QObject,
                      depth: int = 0) -> None:
    """Recursive method for get_all_objects to get Qt objects."""
    for kid in obj.findChildren(QObject, '', Qt.FindChildOption.FindDirectChildrenOnly):
        lines.append('    ' * depth + repr(kid))
        _get_pyqt_objects(lines, kid, depth + 1)


def get_all_objects(start_obj: QObject = None, *, qapp: QApplication = None) -> str:
    """Get all children of an object recursively as a string."""
    if qapp is None:
        assert objects.qapp is not None
        qapp = objects.qapp
    output = ['']
    widget_lines = _get_widgets(qapp)
    widget_lines = ['    ' + e for e in widget_lines]
    widget_lines.insert(0, "Qt widgets - {} objects:".format(
        len(widget_lines)))
    output += widget_lines

    if start_obj is None:
        start_obj = qapp

    pyqt_lines: list[str] = []
    _get_pyqt_objects(pyqt_lines, start_obj)
    pyqt_lines = ['    ' + e for e in pyqt_lines]
    pyqt_lines.insert(0, 'Qt objects - {} objects:'.format(len(pyqt_lines)))

    output += ['']
    output += pyqt_lines
    output += objreg.dump_objects()
    return '\n'.join(output)
