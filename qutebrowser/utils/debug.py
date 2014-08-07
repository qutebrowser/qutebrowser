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

"""Utilities used for debugging."""

import re
import pdb
import sys
import types
from functools import wraps

from PyQt5.QtCore import pyqtRemoveInputHook, QEvent, QCoreApplication

from qutebrowser.utils.misc import elide, compact_text
from qutebrowser.utils.log import misc as logger
import qutebrowser.commands.utils as cmdutils


@cmdutils.register(debug=True, name='debug-set-trace')
def set_trace():
    """Break into the debugger in the shell.

    //

    Based on http://stackoverflow.com/a/1745965/2085149
    """
    if sys.stdout is not None:
        sys.stdout.flush()
    print()
    print("When done debugging, remember to execute:")
    print("  from PyQt5 import QtCore; QtCore.pyqtRestoreInputHook()")
    print("before executing c(ontinue).")
    pyqtRemoveInputHook()
    pdb.set_trace()


@cmdutils.register(debug=True)
def debug_crash(typ='exception'):
    """Crash for debugging purposes.

    Args:
        typ: either 'exception' or 'segfault'.

    Raises:
        raises Exception when typ is not segfault.
        segfaults when typ is (you don't say...)
    """
    if typ == 'segfault':
        # From python's Lib/test/crashers/bogus_code_obj.py
        co = types.CodeType(0, 0, 0, 0, 0, b'\x04\x71\x00\x00', (), (), (),
                            '', '', 1, b'')
        exec(co)  # pylint: disable=exec-used
        raise Exception("Segfault failed (wat.)")
    else:
        raise Exception("Forced crash")


@cmdutils.register(debug=True)
def debug_all_widgets():
    """Print a list of all widgets to debug log."""
    s = QCoreApplication.instance().get_all_widgets()
    logger.debug(s)


@cmdutils.register(debug=True)
def debug_all_objects():
    """Print a list of  all objects to the debug log."""
    s = QCoreApplication.instance().get_all_objects()
    logger.debug(s)


def log_events(klass):
    """Class decorator to log Qt events."""
    old_event = klass.event

    @wraps(old_event)
    def new_event(self, e, *args, **kwargs):
        """Wrapper for event() which logs events."""
        logger.debug("Event in {}: {}".format(klass.__name__,
                                              qenum_key(QEvent, e.type())))
        return old_event(self, e, *args, **kwargs)

    klass.event = new_event
    return klass


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
                arg = compact_text(str(arg), 200)
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


def signal_name(sig):
    """Get a cleaned up name of a signal.

    Args:
        sig: The pyqtSignal

    Return:
        The cleaned up signal name.
    """
    m = re.match(r'[0-9]+(.*)\(.*\)', sig.signal)
    return m.group(1)


def dbg_signal(sig, args):
    """Get a string representation of a signal for debugging.

    Args:
        sig: A pyqtSignal.
        args: The arguments as list of strings.

    Return:
        A human-readable string representation of signal/args.
    """
    argstr = ', '.join([elide(str(a).replace('\n', ' '), 20) for a in args])
    return '{}({})'.format(signal_name(sig), argstr)
