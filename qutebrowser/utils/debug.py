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

import sys
import types
from functools import wraps

from PyQt5.QtCore import (pyqtRemoveInputHook, QEvent, QCoreApplication,
                          QObject)

from qutebrowser.utils.log import misc as logger


try:
    # pylint: disable=import-error
    from ipdb import set_trace as pdb_set_trace
except ImportError:
    from pdb import set_trace as pdb_set_trace

import qutebrowser.commands.utils as cmdutils


@cmdutils.register(debug=True)
def debug_set_trace():
    """Set a tracepoint in the Python debugger that works with Qt.

    Based on http://stackoverflow.com/a/1745965/2085149
    """
    if sys.stdout is not None:
        sys.stdout.flush()
    print()
    print("When done debugging, remember to execute:")
    print("  from PyQt5 import QtCore; QtCore.pyqtRestoreInputHook()")
    print("before executing c(ontinue).")
    pyqtRemoveInputHook()
    pdb_set_trace()


@cmdutils.register(debug=True)
def debug_crash(typ='exception'):
    """Crash for debugging purposes.

    Args:
        typ: either 'exception' or 'segfault'

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
    widgets = QCoreApplication.instance().allWidgets()
    logger.debug("{} widgets".format(len(widgets)))
    widgets.sort(key=lambda e: repr(e))
    for w in widgets:
        logger.debug(repr(w))


@cmdutils.register(debug=True)
def debug_all_objects(obj=None, depth=0):
    """Dump all children of an object recursively."""
    if obj is None:
        obj = QCoreApplication.instance()
    for kid in obj.findChildren(QObject):
        logger.debug('    ' * depth + repr(kid))
        debug_all_objects(kid, depth + 1)


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
    def trace(frame, event, _):
        """Trace function passed to sys.settrace.

        Return:
            Itself, so tracing continues.
        """
        print("{}, {}:{}".format(event, frame.f_code.co_filename,
                                 frame.f_lineno))
        return trace
    if do_trace:
        sys.settrace(trace)
    else:
        sys.settrace(None)


def qenum_key(base, value):
    """Convert a Qt Enum value to its key as a string.

    Args:
        base: The object the enum is in, e.g. QFrame.
        value: The value to get.

    Return:
        The key associated with the value as a string, or None.
    """
    klass = value.__class__
    try:
        idx = klass.staticMetaObject.indexOfEnumerator(klass.__name__)
    except AttributeError:
        idx = -1
    if idx != -1:
        return klass.staticMetaObject.enumerator(idx).valueToKey(value)
    else:
        for name, obj in vars(base).items():
            if isinstance(obj, klass) and obj == value:
                return name
        return None
