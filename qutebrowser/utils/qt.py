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

"""Misc. utilities related to Qt.

Module attributes:
    MAXVALS: A dictionary of C/Qt types (as string) mapped to their maximum
             value.
    MINVALS: A dictionary of C/Qt types (as string) mapped to their minimum
             value.
"""


import os
import sys
import operator
from distutils.version import StrictVersion as Version

from PyQt5.QtCore import QEventLoop, qVersion


MAXVALS = {
    'int': 2 ** 31 - 1,
    'int64': 2 ** 63 - 1,
}

MINVALS = {
    'int': -(2 ** 31),
    'int64': -(2 ** 63),
}


def qt_version_check(version, op=operator.ge):
    """Check if the Qt runtime version is the version supplied or newer.

    Args:
        version: The version to check against.
        op: The operator to use for the check.
    """
    return op(Version(qVersion()), Version(version))


def check_overflow(arg, ctype, fatal=True):
    """Check if the given argument is in bounds for the given type.

    Args:
        arg: The argument to check
        ctype: The C/Qt type to check as a string.
        fatal: Wether to raise exceptions (True) or truncate values (False)

    Return
        The truncated argument if fatal=False
        The original argument if it's in bounds.

    Raise:
        OverflowError if the argument is out of bounds and fatal=True.
    """
    # FIXME we somehow should have nicer exceptions...
    maxval = MAXVALS[ctype]
    minval = MINVALS[ctype]
    if arg > maxval:
        if fatal:
            raise OverflowError(arg)
        else:
            return maxval
    elif arg < minval:
        if fatal:
            raise OverflowError(arg)
        else:
            return minval
    else:
        return arg


def get_qt_args(namespace):
    """Get the Qt QApplication arguments based on an argparse namespace.

    Args:
        namespace: The argparse namespace.

    Return:
        The argv list to be passed to Qt.
    """
    argv = [sys.argv[0]]
    for argname, val in vars(namespace).items():
        if not argname.startswith('qt_'):
            continue
        elif val is None:
            # flag/argument not given
            continue
        elif val is True:
            argv.append('-' + argname[3:])
        else:
            argv.append('-' + argname[3:])
            argv.append(val[0])
    return argv


def check_print_compat():
    """Check if printing should work in the given Qt version."""
    return not (os.name == 'nt' and qt_version_check('5.3.0', operator.lt))


def qt_ensure_valid(obj):
    """Ensure a Qt object with an .isValid() method is valid.

    Raise:
        QtValueError if the object is invalid.
    """
    if not obj.isValid():
        raise QtValueError(obj)


class QtValueError(ValueError):

    """Exception which gets raised by qt_ensure_valid."""

    def __init__(self, obj):
        try:
            self.reason = obj.errorString()
        except AttributeError:
            self.reason = None
        err = "{} is not valid".format(obj)
        if self.reason:
            err += ": {}".format(self.reason)
        super().__init__(err)


class EventLoop(QEventLoop):

    """A thin wrapper around QEventLoop.

    Raises an exception when doing exec_() multiple times.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._executing = False

    def exec_(self, flags=QEventLoop.AllEvents):
        """Override exec_ to raise an exception when re-running."""
        if self._executing:
            raise AssertionError("Eventloop is already running!")
        self._executing = True
        super().exec_(flags)
        self._executing = False
