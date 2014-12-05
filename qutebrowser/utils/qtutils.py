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
import distutils.version  # pylint: disable=no-name-in-module,import-error
# https://bitbucket.org/logilab/pylint/issue/73/

from PyQt5.QtCore import (qVersion, QEventLoop, QDataStream, QByteArray,
                          QIODevice)


MAXVALS = {
    'int': 2 ** 31 - 1,
    'int64': 2 ** 63 - 1,
}

MINVALS = {
    'int': -(2 ** 31),
    'int64': -(2 ** 63),
}


def version_check(version, op=operator.ge):
    """Check if the Qt runtime version is the version supplied or newer.

    Args:
        version: The version to check against.
        op: The operator to use for the check.
    """
    return op(distutils.version.StrictVersion(qVersion()),
              distutils.version.StrictVersion(version))


def check_overflow(arg, ctype, fatal=True):
    """Check if the given argument is in bounds for the given type.

    Args:
        arg: The argument to check
        ctype: The C/Qt type to check as a string.
        fatal: Wether to raise exceptions (True) or truncate values (False)

    Return
        The truncated argument if fatal=False
        The original argument if it's in bounds.
    """
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


def get_args(namespace):
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
    # WORKAROUND (remove this when we bump the requirements to 5.3.0)
    return not (os.name == 'nt' and version_check('5.3.0', operator.lt))


def ensure_valid(obj):
    """Ensure a Qt object with an .isValid() method is valid."""
    if not obj.isValid():
        raise QtValueError(obj)


def _check_qdatastream(stream):
    """Check the status of a QDataStream and raise IOError if it's not ok."""
    status_to_str = {
        QDataStream.Ok: "The data stream is operating normally.",
        QDataStream.ReadPastEnd: ("The data stream has read past the end of "
                                  "the data in the underlying device."),
        QDataStream.ReadCorruptData: "The data stream has read corrupt data.",
        QDataStream.WriteFailed: ("The data stream cannot write to the "
                                  "underlying device."),
    }
    if stream.status() != QDataStream.Ok:
        raise IOError(status_to_str[stream.status()])


def serialize(obj):
    """Serialize an object into a QByteArray."""
    data = QByteArray()
    stream = QDataStream(data, QIODevice.WriteOnly)
    stream << obj  # pylint: disable=pointless-statement
    _check_qdatastream(stream)
    return data


def deserialize(data, obj):
    """Deserialize an object from a QByteArray."""
    stream = QDataStream(data, QIODevice.ReadOnly)
    stream >> obj  # pylint: disable=pointless-statement
    _check_qdatastream(stream)


class QtValueError(ValueError):

    """Exception which gets raised by ensure_valid."""

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
