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
import logging
from functools import wraps

from PyQt5.QtCore import pyqtRemoveInputHook, QEvent

try:
    # pylint: disable=import-error
    from ipdb import set_trace as pdb_set_trace
except ImportError:
    from pdb import set_trace as pdb_set_trace

import qutebrowser.commands.utils as cmdutils

EVENTS = {n: x for x, n in vars(QEvent).items()
          if isinstance(n, QEvent.Type)}


def log_events(klass):
    """Class decorator to log Qt events."""
    old_event = klass.event

    @wraps(old_event)
    def new_event(self, e, *args, **kwargs):
        """Wrapper for event() which logs events."""
        logging.debug("Event in {}: {}".format(klass.__name__,
                                               EVENTS[e.type()]))
        return old_event(self, e, *args, **kwargs)

    klass.event = new_event
    return klass


@cmdutils.register(name='set-trace', hide=True)
def set_trace():
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
