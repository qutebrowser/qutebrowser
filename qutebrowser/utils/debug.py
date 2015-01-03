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

"""Utilities used for debugging."""

import re
import sys
import inspect
import functools

from PyQt5.QtCore import QEvent, QMetaMethod

from qutebrowser.utils import log, utils, qtutils


def log_events(klass):
    """Class decorator to log Qt events."""
    old_event = klass.event

    @functools.wraps(old_event)
    def new_event(self, e, *args, **kwargs):
        """Wrapper for event() which logs events."""
        log.misc.debug("Event in {}: {}".format(utils.qualname(klass),
                                                qenum_key(QEvent, e.type())))
        return old_event(self, e, *args, **kwargs)

    klass.event = new_event
    return klass


def log_signals(obj):
    """Log all signals of an object or class.

    Can be used as class decorator.
    """

    def log_slot(obj, signal, *args):
        """Slot connected to a signal to log it."""
        dbg = dbg_signal(signal, args)
        try:
            r = repr(obj)
        except RuntimeError:
            r = '<deleted>'
        log.misc.debug("Signal in {}: {}".format(r, dbg))

    def connect_log_slot(obj):
        """Helper function to connect all signals to a logging slot."""
        metaobj = obj.metaObject()
        for i in range(metaobj.methodCount()):
            meta_method = metaobj.method(i)
            qtutils.ensure_valid(meta_method)
            if meta_method.methodType() == QMetaMethod.Signal:
                name = bytes(meta_method.name()).decode('ascii')
                signal = getattr(obj, name)
                signal.connect(functools.partial(log_slot, obj, signal))

    if inspect.isclass(obj):
        old_init = obj.__init__

        @functools.wraps(old_init)
        def new_init(self, *args, **kwargs):
            """Wrapper for __init__() which logs signals."""
            ret = old_init(self, *args, **kwargs)
            connect_log_slot(self)
            return ret

        obj.__init__ = new_init
        return obj
    else:
        connect_log_slot(obj)


def trace_lines(do_trace):
    """Turn on/off printing each executed line.

    Args:
        do_trace: Whether to start tracing (True) or stop it (False).
    """
    def trace(frame, event, arg):
        """Trace function passed to sys.settrace.

        Return:
            Itself, so tracing continues.
        """
        if sys is not None:
            loc = '{}:{}'.format(frame.f_code.co_filename, frame.f_lineno)
            if arg is not None:
                arg = utils.compact_text(str(arg), 200)
            else:
                arg = ''
            print("{:11} {:80} {}".format(event, loc, arg), file=sys.stderr)
            return trace
        else:
            # When tracing while shutting down, it seems sys can be None
            # sometimes... if that's the case, we stop tracing.
            return None
    if do_trace:
        sys.settrace(trace)
    else:
        sys.settrace(None)


def qenum_key(base, value, add_base=False, klass=None):
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
        idx = klass.staticMetaObject.indexOfEnumerator(klass.__name__)
    except AttributeError:
        idx = -1
    if idx != -1:
        ret = klass.staticMetaObject.enumerator(idx).valueToKey(value)
    else:
        for name, obj in vars(base).items():
            if isinstance(obj, klass) and obj == value:
                ret = name
                break
        else:
            ret = '0x{:04x}'.format(int(value))
    if add_base and hasattr(base, '__name__'):
        return '.'.join([base.__name__, ret])
    else:
        return ret


def qflags_key(base, value, add_base=False, klass=None):
    """Convert a Qt QFlags value to its keys as string.

    Note: Passing a combined value (such as Qt.AlignCenter) will get the names
    for the individual bits (e.g. Qt.AlignVCenter | Qt.AlignHCenter). FIXME

    https://github.com/The-Compiler/qutebrowser/issues/42

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
    bits = []
    names = []
    mask = 0x01
    value = int(value)
    while mask < value:
        if value & mask:
            bits.append(mask)
        mask <<= 1
    for bit in bits:
        # We have to re-convert to an enum type here or we'll sometimes get an
        # empty string back.
        names.append(qenum_key(base, klass(bit), add_base))
    return '|'.join(names)


def signal_name(sig):
    """Get a cleaned up name of a signal.

    Args:
        sig: The pyqtSignal

    Return:
        The cleaned up signal name.
    """
    m = re.match(r'[0-9]+(.*)\(.*\)', sig.signal)
    return m.group(1)


def _format_args(args=None, kwargs=None):
    """Format a list of arguments/kwargs to a function-call like string."""
    if args is not None:
        arglist = [utils.compact_text(repr(arg), 200) for arg in args]
    else:
        arglist = []
    if kwargs is not None:
        for k, v in kwargs.items():
            arglist.append('{}={}'.format(k, utils.compact_text(repr(v), 200)))
    return ', '.join(arglist)


def dbg_signal(sig, args):
    """Get a string representation of a signal for debugging.

    Args:
        sig: A pyqtSignal.
        args: The arguments as list of strings.

    Return:
        A human-readable string representation of signal/args.
    """
    return '{}({})'.format(signal_name(sig), _format_args(args))


def format_call(func, args=None, kwargs=None, full=True):
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
    return '{}({})'.format(name, _format_args(args, kwargs))
