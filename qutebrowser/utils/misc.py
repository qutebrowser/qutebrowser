"""Other utilities which don't fit anywhere else."""

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

import re

from PyQt5.QtCore import pyqtRemoveInputHook

try:
    from ipdb import set_trace as pdb_set_trace
except ImportError:
    from pdb import set_trace as pdb_set_trace


def dbg_signal(sig, args):
    """Return a string representation of a signal for debugging.

    sig -- A pyqtSignal.
    args -- The arguments as list of strings.

    """
    m = re.match(r'[0-9]+(.*)\(.*\)', sig.signal)
    signame = m.group(1)
    return '{}({})'.format(signame, ', '.join(map(str, args)))


def set_trace():
    """
    Set a tracepoint in the Python debugger that works with Qt.

    Based on http://stackoverflow.com/a/1745965/2085149

    """
    print()
    print("When done debugging, remember to execute:")
    print("  from PyQt5 import QtCore; QtCore.pyqtRestoreInputHook()")
    print("before executing c(ontinue).")
    pyqtRemoveInputHook()
    return pdb_set_trace()
