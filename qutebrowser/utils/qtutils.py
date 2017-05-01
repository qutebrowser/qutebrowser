# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


import io
import os
import sys
import operator
import contextlib

from PyQt5.QtCore import (qVersion, QEventLoop, QDataStream, QByteArray,
                          QIODevice, QSaveFile, QT_VERSION_STR)
from PyQt5.QtWidgets import QApplication
try:
    from PyQt5.QtWebKit import qWebKitVersion
except ImportError:  # pragma: no cover
    qWebKitVersion = None

from qutebrowser.utils import log

with log.ignore_py_warnings(category=PendingDeprecationWarning, module='imp'):
    with log.ignore_py_warnings(category=ImportWarning):
        # This imports 'imp' and gives us a PendingDeprecationWarning on
        # Debian Jessie.
        #
        # On Archlinux, we get ImportWarning from
        # importlib/_bootstrap_external.py for modules with missing __init__.
        import pkg_resources


MAXVALS = {
    'int': 2 ** 31 - 1,
    'int64': 2 ** 63 - 1,
}

MINVALS = {
    'int': -(2 ** 31),
    'int64': -(2 ** 63),
}


class QtOSError(OSError):

    """An OSError triggered by a QFileDevice.

    Attributes:
        qt_errno: The error attribute of the given QFileDevice, if applicable.
    """

    def __init__(self, dev, msg=None):
        if msg is None:
            msg = dev.errorString()

        super().__init__(msg)

        try:
            self.qt_errno = dev.error()
        except AttributeError:
            self.qt_errno = None


def version_check(version, exact=False, strict=False):
    """Check if the Qt runtime version is the version supplied or newer.

    Args:
        version: The version to check against.
        exact: if given, check with == instead of >=
        strict: If given, also check the compiled Qt version.
    """
    # Catch code using the old API for this
    assert exact not in [operator.gt, operator.lt, operator.ge, operator.le,
                         operator.eq], exact
    parsed = pkg_resources.parse_version(version)
    op = operator.eq if exact else operator.ge
    result = op(pkg_resources.parse_version(qVersion()), parsed)
    if strict and result:
        # v1 ==/>= parsed, now check if v2 ==/>= parsed too.
        result = op(pkg_resources.parse_version(QT_VERSION_STR), parsed)
    return result


def is_qtwebkit_ng():
    """Check if the given version is QtWebKit-NG."""
    assert qWebKitVersion is not None
    return (pkg_resources.parse_version(qWebKitVersion()) >
            pkg_resources.parse_version('538.1'))


def check_overflow(arg, ctype, fatal=True):
    """Check if the given argument is in bounds for the given type.

    Args:
        arg: The argument to check
        ctype: The C/Qt type to check as a string.
        fatal: Whether to raise exceptions (True) or truncate values (False)

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

    if namespace.qt_flag is not None:
        argv += ['--' + flag[0] for flag in namespace.qt_flag]

    if namespace.qt_arg is not None:
        for name, value in namespace.qt_arg:
            argv += ['--' + name, value]

    return argv


def check_print_compat():
    """Check if printing should work in the given Qt version."""
    # WORKAROUND (remove this when we bump the requirements to 5.3.0)
    if os.name == 'nt':
        return version_check('5.3')
    else:
        return True


def ensure_valid(obj):
    """Ensure a Qt object with an .isValid() method is valid."""
    if not obj.isValid():
        raise QtValueError(obj)


def check_qdatastream(stream):
    """Check the status of a QDataStream and raise OSError if it's not ok."""
    status_to_str = {
        QDataStream.Ok: "The data stream is operating normally.",
        QDataStream.ReadPastEnd: ("The data stream has read past the end of "
                                  "the data in the underlying device."),
        QDataStream.ReadCorruptData: "The data stream has read corrupt data.",
        QDataStream.WriteFailed: ("The data stream cannot write to the "
                                  "underlying device."),
    }
    if stream.status() != QDataStream.Ok:
        raise OSError(status_to_str[stream.status()])


def serialize(obj):
    """Serialize an object into a QByteArray."""
    data = QByteArray()
    stream = QDataStream(data, QIODevice.WriteOnly)
    serialize_stream(stream, obj)
    return data


def deserialize(data, obj):
    """Deserialize an object from a QByteArray."""
    stream = QDataStream(data, QIODevice.ReadOnly)
    deserialize_stream(stream, obj)


def serialize_stream(stream, obj):
    """Serialize an object into a QDataStream."""
    check_qdatastream(stream)
    stream << obj  # pylint: disable=pointless-statement
    check_qdatastream(stream)


def deserialize_stream(stream, obj):
    """Deserialize a QDataStream into an object."""
    check_qdatastream(stream)
    stream >> obj  # pylint: disable=pointless-statement
    check_qdatastream(stream)


@contextlib.contextmanager
def savefile_open(filename, binary=False, encoding='utf-8'):
    """Context manager to easily use a QSaveFile."""
    f = QSaveFile(filename)
    cancelled = False
    try:
        open_ok = f.open(QIODevice.WriteOnly)
        if not open_ok:
            raise QtOSError(f)
        if binary:
            new_f = PyQIODevice(f)
        else:
            new_f = io.TextIOWrapper(PyQIODevice(f), encoding=encoding)
        yield new_f
        new_f.flush()
    except:
        f.cancelWriting()
        cancelled = True
        raise
    finally:
        commit_ok = f.commit()
        if not commit_ok and not cancelled:
            raise QtOSError(f, msg="Commit failed!")


@contextlib.contextmanager
def unset_organization():
    """Temporarily unset QApplication.organizationName().

    This is primarily needed in config.py.
    """
    qapp = QApplication.instance()
    orgname = qapp.organizationName()
    qapp.setOrganizationName(None)
    try:
        yield
    finally:
        qapp.setOrganizationName(orgname)


class PyQIODevice(io.BufferedIOBase):

    """Wrapper for a QIODevice which provides a python interface.

    Attributes:
        dev: The underlying QIODevice.
    """

    def __init__(self, dev):
        super().__init__()
        self.dev = dev

    def __len__(self):
        return self.dev.size()

    def _check_open(self):
        """Check if the device is open, raise ValueError if not."""
        if not self.dev.isOpen():
            raise ValueError("IO operation on closed device!")

    def _check_random(self):
        """Check if the device supports random access, raise OSError if not."""
        if not self.seekable():
            raise OSError("Random access not allowed!")

    def _check_readable(self):
        """Check if the device is readable, raise OSError if not."""
        if not self.dev.isReadable():
            raise OSError("Trying to read unreadable file!")

    def _check_writable(self):
        """Check if the device is writable, raise OSError if not."""
        if not self.writable():
            raise OSError("Trying to write to unwritable file!")

    def open(self, mode):
        """Open the underlying device and ensure opening succeeded.

        Raises OSError if opening failed.

        Args:
            mode: QIODevice::OpenMode flags.

        Return:
            A contextlib.closing() object so this can be used as
            contextmanager.
        """
        ok = self.dev.open(mode)
        if not ok:
            raise QtOSError(self.dev)
        return contextlib.closing(self)

    def close(self):
        """Close the underlying device."""
        self.dev.close()

    def fileno(self):
        raise io.UnsupportedOperation

    def seek(self, offset, whence=io.SEEK_SET):
        self._check_open()
        self._check_random()
        if whence == io.SEEK_SET:
            ok = self.dev.seek(offset)
        elif whence == io.SEEK_CUR:
            ok = self.dev.seek(self.tell() + offset)
        elif whence == io.SEEK_END:
            ok = self.dev.seek(len(self) + offset)
        else:
            raise io.UnsupportedOperation("whence = {} is not "
                                          "supported!".format(whence))
        if not ok:
            raise QtOSError(self.dev, msg="seek failed!")

    def truncate(self, size=None):  # pylint: disable=unused-argument
        raise io.UnsupportedOperation

    @property
    def closed(self):
        return not self.dev.isOpen()

    def flush(self):
        self._check_open()
        self.dev.waitForBytesWritten(-1)

    def isatty(self):
        self._check_open()
        return False

    def readable(self):
        return self.dev.isReadable()

    def readline(self, size=-1):
        self._check_open()
        self._check_readable()

        if size < 0:
            qt_size = 0  # no maximum size
        elif size == 0:
            return QByteArray()
        else:
            qt_size = size + 1  # Qt also counts the NUL byte

        if self.dev.canReadLine():
            buf = self.dev.readLine(qt_size)
        else:
            if size < 0:
                buf = self.dev.readAll()
            else:
                buf = self.dev.read(size)

        if buf is None:
            raise QtOSError(self.dev)
        return buf

    def seekable(self):
        return not self.dev.isSequential()

    def tell(self):
        self._check_open()
        self._check_random()
        return self.dev.pos()

    def writable(self):
        return self.dev.isWritable()

    def write(self, b):
        self._check_open()
        self._check_writable()
        num = self.dev.write(b)
        if num == -1 or num < len(b):
            raise QtOSError(self.dev)
        return num

    def read(self, size=-1):
        self._check_open()
        self._check_readable()
        if size < 0:
            buf = self.dev.readAll()
        else:
            buf = self.dev.read(size)
        if buf is None:
            raise QtOSError(self.dev)
        return buf


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
