# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
    MAX_WORLD_ID: The highest world ID allowed in this version of QtWebEngine.
"""


import io
import operator
import contextlib
import typing

import pkg_resources
from PyQt5.QtCore import (qVersion, QEventLoop, QDataStream, QByteArray,
                          QIODevice, QFileDevice, QSaveFile, QT_VERSION_STR,
                          PYQT_VERSION_STR, QObject, QUrl)
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication
try:
    from PyQt5.QtWebKit import qWebKitVersion
except ImportError:  # pragma: no cover
    qWebKitVersion = None  # type: ignore[assignment]  # noqa: N816

from qutebrowser.misc import objects
from qutebrowser.utils import usertypes


MAXVALS = {
    'int': 2 ** 31 - 1,
    'int64': 2 ** 63 - 1,
}

MINVALS = {
    'int': -(2 ** 31),
    'int64': -(2 ** 63),
}


class QtOSError(OSError):

    """An OSError triggered by a QIODevice.

    Attributes:
        qt_errno: The error attribute of the given QFileDevice, if applicable.
    """

    def __init__(self, dev: QIODevice, msg: str = None) -> None:
        if msg is None:
            msg = dev.errorString()

        self.qt_errno = None  # type: typing.Optional[QFileDevice.FileError]
        if isinstance(dev, QFileDevice):
            msg = self._init_filedev(dev, msg)

        super().__init__(msg)

    def _init_filedev(self, dev: QFileDevice, msg: str) -> str:
        self.qt_errno = dev.error()
        filename = dev.fileName()
        msg += ": {!r}".format(filename)
        return msg


def version_check(version: str,
                  exact: bool = False,
                  compiled: bool = True) -> bool:
    """Check if the Qt runtime version is the version supplied or newer.

    Args:
        version: The version to check against.
        exact: if given, check with == instead of >=
        compiled: Set to False to not check the compiled version.
    """
    if compiled and exact:
        raise ValueError("Can't use compiled=True with exact=True!")

    parsed = pkg_resources.parse_version(version)
    op = operator.eq if exact else operator.ge
    result = op(pkg_resources.parse_version(qVersion()), parsed)
    if compiled and result:
        # qVersion() ==/>= parsed, now check if QT_VERSION_STR ==/>= parsed.
        result = op(pkg_resources.parse_version(QT_VERSION_STR), parsed)
    if compiled and result:
        # FInally, check PYQT_VERSION_STR as well.
        result = op(pkg_resources.parse_version(PYQT_VERSION_STR), parsed)
    return result


# WORKAROUND for https://bugreports.qt.io/browse/QTBUG-69904
MAX_WORLD_ID = 256 if version_check('5.11.2') else 11


def is_new_qtwebkit() -> bool:
    """Check if the given version is a new QtWebKit."""
    assert qWebKitVersion is not None
    return (pkg_resources.parse_version(qWebKitVersion()) >
            pkg_resources.parse_version('538.1'))


def is_single_process() -> bool:
    """Check whether QtWebEngine is running in single-process mode."""
    if objects.backend == usertypes.Backend.QtWebKit:
        return False
    args = QApplication.instance().arguments()
    return '--single-process' in args


def check_overflow(arg: int, ctype: str, fatal: bool = True) -> int:
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
        return maxval
    elif arg < minval:
        if fatal:
            raise OverflowError(arg)
        return minval
    else:
        return arg


if typing.TYPE_CHECKING:
    class Validatable(typing.Protocol):

        """An object with an isValid() method (e.g. QUrl)."""

        def isValid(self) -> bool:
            ...


def ensure_valid(obj: 'Validatable') -> None:
    """Ensure a Qt object with an .isValid() method is valid."""
    if not obj.isValid():
        raise QtValueError(obj)


def check_qdatastream(stream: QDataStream) -> None:
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


_QtSerializableType = typing.Union[QObject, QByteArray, QUrl]


def serialize(obj: _QtSerializableType) -> QByteArray:
    """Serialize an object into a QByteArray."""
    data = QByteArray()
    stream = QDataStream(data, QIODevice.WriteOnly)
    serialize_stream(stream, obj)
    return data


def deserialize(data: QByteArray, obj: _QtSerializableType) -> None:
    """Deserialize an object from a QByteArray."""
    stream = QDataStream(data, QIODevice.ReadOnly)
    deserialize_stream(stream, obj)


def serialize_stream(stream: QDataStream, obj: _QtSerializableType) -> None:
    """Serialize an object into a QDataStream."""
    # pylint: disable=pointless-statement
    check_qdatastream(stream)
    stream << obj  # type: ignore[operator]
    check_qdatastream(stream)


def deserialize_stream(stream: QDataStream, obj: _QtSerializableType) -> None:
    """Deserialize a QDataStream into an object."""
    # pylint: disable=pointless-statement
    check_qdatastream(stream)
    stream >> obj  # type: ignore[operator]
    check_qdatastream(stream)


@contextlib.contextmanager
def savefile_open(
        filename: str,
        binary: bool = False,
        encoding: str = 'utf-8'
) -> typing.Iterator[typing.IO]:
    """Context manager to easily use a QSaveFile."""
    f = QSaveFile(filename)
    cancelled = False
    try:
        open_ok = f.open(QIODevice.WriteOnly)
        if not open_ok:
            raise QtOSError(f)

        dev = typing.cast(typing.IO[bytes], PyQIODevice(f))

        if binary:
            new_f = dev  # type: typing.IO
        else:
            new_f = io.TextIOWrapper(dev, encoding=encoding)

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


def qcolor_to_qsscolor(c: QColor) -> str:
    """Convert a QColor to a string that can be used in a QStyleSheet."""
    ensure_valid(c)
    return "rgba({}, {}, {}, {})".format(
        c.red(), c.green(), c.blue(), c.alpha())


class PyQIODevice(io.BufferedIOBase):

    """Wrapper for a QIODevice which provides a python interface.

    Attributes:
        dev: The underlying QIODevice.
    """

    def __init__(self, dev: QIODevice) -> None:
        super().__init__()
        self.dev = dev

    def __len__(self) -> int:
        return self.dev.size()

    def _check_open(self) -> None:
        """Check if the device is open, raise ValueError if not."""
        if not self.dev.isOpen():
            raise ValueError("IO operation on closed device!")

    def _check_random(self) -> None:
        """Check if the device supports random access, raise OSError if not."""
        if not self.seekable():
            raise OSError("Random access not allowed!")

    def _check_readable(self) -> None:
        """Check if the device is readable, raise OSError if not."""
        if not self.dev.isReadable():
            raise OSError("Trying to read unreadable file!")

    def _check_writable(self) -> None:
        """Check if the device is writable, raise OSError if not."""
        if not self.writable():
            raise OSError("Trying to write to unwritable file!")

    def open(self, mode: QIODevice.OpenMode) -> contextlib.closing:
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

    def close(self) -> None:
        """Close the underlying device."""
        self.dev.close()

    def fileno(self) -> int:
        raise io.UnsupportedOperation

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
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

        return self.dev.pos()

    def truncate(self, size: int = None) -> int:
        raise io.UnsupportedOperation

    @property
    def closed(self) -> bool:
        return not self.dev.isOpen()

    def flush(self) -> None:
        self._check_open()
        self.dev.waitForBytesWritten(-1)

    def isatty(self) -> bool:
        self._check_open()
        return False

    def readable(self) -> bool:
        return self.dev.isReadable()

    def readline(self, size: int = -1) -> bytes:
        self._check_open()
        self._check_readable()

        if size < 0:
            qt_size = 0  # no maximum size
        elif size == 0:
            return b''
        else:
            qt_size = size + 1  # Qt also counts the NUL byte

        buf = None  # type: typing.Union[QByteArray, bytes, None]
        if self.dev.canReadLine():
            buf = self.dev.readLine(qt_size)
        elif size < 0:
            buf = self.dev.readAll()
        else:
            buf = self.dev.read(size)

        if buf is None:
            raise QtOSError(self.dev)

        if isinstance(buf, QByteArray):
            # The type (bytes or QByteArray) seems to depend on what data we
            # feed in...
            buf = buf.data()

        return buf

    def seekable(self) -> bool:
        return not self.dev.isSequential()

    def tell(self) -> int:
        self._check_open()
        self._check_random()
        return self.dev.pos()

    def writable(self) -> bool:
        return self.dev.isWritable()

    def write(self, data: typing.Union[bytes, bytearray]) -> int:
        self._check_open()
        self._check_writable()
        num = self.dev.write(data)
        if num == -1 or num < len(data):
            raise QtOSError(self.dev)
        return num

    def read(self, size: typing.Optional[int] = None) -> bytes:
        self._check_open()
        self._check_readable()

        buf = None  # type: typing.Union[QByteArray, bytes, None]
        if size in [None, -1]:
            buf = self.dev.readAll()
        else:
            assert size is not None
            buf = self.dev.read(size)

        if buf is None:
            raise QtOSError(self.dev)

        if isinstance(buf, QByteArray):
            # The type (bytes or QByteArray) seems to depend on what data we
            # feed in...
            buf = buf.data()

        return buf


class QtValueError(ValueError):

    """Exception which gets raised by ensure_valid."""

    def __init__(self, obj: 'Validatable') -> None:
        try:
            self.reason = obj.errorString()  # type: ignore[attr-defined]
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

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self._executing = False

    def exec_(
            self,
            flags: QEventLoop.ProcessEventsFlags =
            typing.cast(QEventLoop.ProcessEventsFlags, QEventLoop.AllEvents)
    ) -> int:
        """Override exec_ to raise an exception when re-running."""
        if self._executing:
            raise AssertionError("Eventloop is already running!")
        self._executing = True
        status = super().exec_(flags)
        self._executing = False
        return status
