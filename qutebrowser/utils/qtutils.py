# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Misc. utilities related to Qt.

Module attributes:
    MAXVALS: A dictionary of C/Qt types (as string) mapped to their maximum
             value.
    MINVALS: A dictionary of C/Qt types (as string) mapped to their minimum
             value.
    MAX_WORLD_ID: The highest world ID allowed by QtWebEngine.
"""


import io
import enum
import pathlib
import operator
import contextlib
from typing import (Any, TYPE_CHECKING, BinaryIO, IO, Literal,
                    Optional, Union, Protocol, cast, overload, TypeVar)
from collections.abc import Iterator

from qutebrowser.qt import machinery, sip
from qutebrowser.qt.core import (qVersion, QEventLoop, QDataStream, QByteArray,
                          QIODevice, QFileDevice, QSaveFile, QT_VERSION_STR,
                          PYQT_VERSION_STR, QObject, QUrl, QLibraryInfo)
from qutebrowser.qt.gui import QColor
try:
    from qutebrowser.qt.webkit import qWebKitVersion
except ImportError:  # pragma: no cover
    qWebKitVersion = None  # type: ignore[assignment]  # noqa: N816
if TYPE_CHECKING:
    from qutebrowser.qt.webkit import QWebHistory
    from qutebrowser.qt.webenginecore import QWebEngineHistory

from qutebrowser.misc import objects
from qutebrowser.utils import usertypes, utils


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

        self.qt_errno: Optional[QFileDevice.FileError] = None
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

    By default this function will check `version` against:

    1. the runtime Qt version (from qVersion())
    2. the Qt version that PyQt was compiled against (from QT_VERSION_STR)
    3. the PyQt version (from PYQT_VERSION_STR)

    With `compiled=False` only the runtime Qt version (1) is checked.

    You can often run older PyQt versions against newer Qt versions, but you
    won't be able to access any APIs that were only added in the newer Qt
    version. So if you want to check if a new feature is supported, use the
    default behavior. If you just want to check the underlying Qt version,
    pass `compiled=False`.

    Args:
        version: The version to check against.
        exact: if given, check with == instead of >=
        compiled: Set to False to not check the compiled Qt version or the
          PyQt version.
    """
    if compiled and exact:
        raise ValueError("Can't use compiled=True with exact=True!")

    parsed = utils.VersionNumber.parse(version)
    op = operator.eq if exact else operator.ge

    qversion = qVersion()
    assert qversion is not None
    result = op(utils.VersionNumber.parse(qversion), parsed)

    if compiled and result:
        # qVersion() ==/>= parsed, now check if QT_VERSION_STR ==/>= parsed.
        result = op(utils.VersionNumber.parse(QT_VERSION_STR), parsed)
    if compiled and result:
        # Finally, check PYQT_VERSION_STR as well.
        result = op(utils.VersionNumber.parse(PYQT_VERSION_STR), parsed)
    return result


MAX_WORLD_ID = 256


def is_new_qtwebkit() -> bool:
    """Check if the given version is a new QtWebKit."""
    assert qWebKitVersion is not None
    return (utils.VersionNumber.parse(qWebKitVersion()) >
            utils.VersionNumber.parse('538.1'))


def is_single_process() -> bool:
    """Check whether QtWebEngine is running in single-process mode."""
    if objects.backend == usertypes.Backend.QtWebKit:
        return False
    assert objects.backend == usertypes.Backend.QtWebEngine, objects.backend
    args = objects.qapp.arguments()
    return '--single-process' in args


def is_wayland() -> bool:
    """Check if we are running on Wayland."""
    return objects.qapp.platformName() in ["wayland", "wayland-egl"]


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


class Validatable(Protocol):

    """An object with an isValid() method (e.g. QUrl)."""

    def isValid(self) -> bool:
        ...


def ensure_valid(obj: Validatable) -> None:
    """Ensure a Qt object with an .isValid() method is valid."""
    if not obj.isValid():
        raise QtValueError(obj)


def check_qdatastream(stream: QDataStream) -> None:
    """Check the status of a QDataStream and raise OSError if it's not ok."""
    status_to_str = {
        QDataStream.Status.Ok: "The data stream is operating normally.",
        QDataStream.Status.ReadPastEnd: ("The data stream has read past the end of "
                                  "the data in the underlying device."),
        QDataStream.Status.ReadCorruptData: "The data stream has read corrupt data.",
        QDataStream.Status.WriteFailed: ("The data stream cannot write to the "
                                  "underlying device."),
    }
    if machinery.IS_QT6:
        try:
            status_to_str[QDataStream.Status.SizeLimitExceeded] = (
                "The data stream cannot read or write the data because its size is larger "
                "than supported by the current platform."
            )
        except AttributeError:
            # Added in Qt 6.7
            pass

    if stream.status() != QDataStream.Status.Ok:
        raise OSError(status_to_str[stream.status()])


_QtSerializableType = Union[
    QObject,
    QByteArray,
    QUrl,
    'QWebEngineHistory',
    'QWebHistory'
]


def serialize(obj: _QtSerializableType) -> QByteArray:
    """Serialize an object into a QByteArray."""
    data = QByteArray()
    stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
    serialize_stream(stream, obj)
    return data


def deserialize(data: QByteArray, obj: _QtSerializableType) -> None:
    """Deserialize an object from a QByteArray."""
    stream = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
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


@overload
@contextlib.contextmanager
def savefile_open(
        filename: str,
        binary: Literal[False] = ...,
        encoding: str = 'utf-8'
) -> Iterator[IO[str]]:
    ...


@overload
@contextlib.contextmanager
def savefile_open(
        filename: str,
        binary: Literal[True],
        encoding: str = 'utf-8'
) -> Iterator[IO[bytes]]:
    ...


@contextlib.contextmanager
def savefile_open(
        filename: str,
        binary: bool = False,
        encoding: str = 'utf-8'
) -> Iterator[Union[IO[str], IO[bytes]]]:
    """Context manager to easily use a QSaveFile."""
    f = QSaveFile(filename)
    cancelled = False
    try:
        open_ok = f.open(QIODevice.OpenModeFlag.WriteOnly)
        if not open_ok:
            raise QtOSError(f)

        dev = cast(BinaryIO, PyQIODevice(f))

        if binary:
            new_f: Union[IO[str], IO[bytes]] = dev
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

    # contextlib.closing is only generic in Python 3.9+
    def open(
        self,
        mode: QIODevice.OpenModeFlag,
    ) -> contextlib.closing:  # type: ignore[type-arg]
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

    def readline(self, size: Optional[int] = -1) -> bytes:
        self._check_open()
        self._check_readable()

        if size is None or size < 0:
            qt_size = None  # no maximum size
        elif size == 0:
            return b''
        else:
            qt_size = size + 1  # Qt also counts the NUL byte

        buf: Union[QByteArray, bytes, None] = None
        if self.dev.canReadLine():
            if qt_size is None:
                buf = self.dev.readLine()
            else:
                buf = self.dev.readLine(qt_size)
        elif size is None or size < 0:
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

    def write(  # type: ignore[override]
            self,
            data: Union[bytes, bytearray]
    ) -> int:
        self._check_open()
        self._check_writable()
        num = self.dev.write(data)
        if num == -1 or num < len(data):
            raise QtOSError(self.dev)
        return num

    def read(self, size: Optional[int] = None) -> bytes:
        self._check_open()
        self._check_readable()

        buf: Union[QByteArray, bytes, None] = None
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

    def __init__(self, obj: Validatable) -> None:
        try:
            self.reason = obj.errorString()  # type: ignore[attr-defined]
        except AttributeError:
            self.reason = None
        err = "{} is not valid".format(obj)
        if self.reason:
            err += ": {}".format(self.reason)
        super().__init__(err)


if machinery.IS_QT6:
    _ProcessEventFlagType = QEventLoop.ProcessEventsFlag
else:
    _ProcessEventFlagType = Union[
        QEventLoop.ProcessEventsFlag, QEventLoop.ProcessEventsFlags]


class EventLoop(QEventLoop):

    """A thin wrapper around QEventLoop.

    Raises an exception when doing exec() multiple times.
    """

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self._executing = False

    def exec(
        self,
        flags: _ProcessEventFlagType = QEventLoop.ProcessEventsFlag.AllEvents,
    ) -> int:
        """Override exec_ to raise an exception when re-running."""
        if self._executing:
            raise AssertionError("Eventloop is already running!")
        self._executing = True
        if machinery.IS_QT5:
            flags = cast(QEventLoop.ProcessEventsFlags, flags)
        status = super().exec(flags)
        self._executing = False
        return status


def _get_color_percentage(  # pylint: disable=too-many-positional-arguments
    x1: int, y1: int, z1: int, a1: int,
    x2: int, y2: int, z2: int, a2: int,
    percent: int
) -> tuple[int, int, int, int]:
    """Get a color which is percent% interpolated between start and end.

    Args:
        x1, y1, z1, a1 : Start color components (R, G, B, A / H, S, V, A / H, S, L, A)
        x2, y2, z2, a2 : End color components (R, G, B, A / H, S, V, A / H, S, L, A)
        percent: Percentage to interpolate, 0-100.
                 0: Start color will be returned.
                 100: End color will be returned.

    Return:
        A (x, y, z, alpha) tuple with the interpolated color components.
    """
    if not 0 <= percent <= 100:
        raise ValueError("percent needs to be between 0 and 100!")
    x = round(x1 + (x2 - x1) * percent / 100)
    y = round(y1 + (y2 - y1) * percent / 100)
    z = round(z1 + (z2 - z1) * percent / 100)
    a = round(a1 + (a2 - a1) * percent / 100)
    return (x, y, z, a)


def interpolate_color(
        start: QColor,
        end: QColor,
        percent: int,
        colorspace: Optional[QColor.Spec] = QColor.Spec.Rgb
) -> QColor:
    """Get an interpolated color value.

    Args:
        start: The start color.
        end: The end color.
        percent: Which value to get (0 - 100)
        colorspace: The desired interpolation color system,
                    QColor::{Rgb,Hsv,Hsl} (from QColor::Spec enum)
                    If None, start is used except when percent is 100.

    Return:
        The interpolated QColor, with the same spec as the given start color.
    """
    ensure_valid(start)
    ensure_valid(end)

    if colorspace is None:
        if percent == 100:
            r, g, b, a = end.getRgb()
            assert r is not None
            assert g is not None
            assert b is not None
            assert a is not None
            return QColor(r, g, b, a)
        else:
            r, g, b, a = start.getRgb()
            assert r is not None
            assert g is not None
            assert b is not None
            assert a is not None
            return QColor(r, g, b, a)

    out = QColor()
    if colorspace == QColor.Spec.Rgb:
        r1, g1, b1, a1 = start.getRgb()
        r2, g2, b2, a2 = end.getRgb()
        assert r1 is not None
        assert g1 is not None
        assert b1 is not None
        assert a1 is not None
        assert r2 is not None
        assert g2 is not None
        assert b2 is not None
        assert a2 is not None
        components = _get_color_percentage(r1, g1, b1, a1, r2, g2, b2, a2, percent)
        out.setRgb(*components)
    elif colorspace == QColor.Spec.Hsv:
        h1, s1, v1, a1 = start.getHsv()
        h2, s2, v2, a2 = end.getHsv()
        assert h1 is not None
        assert s1 is not None
        assert v1 is not None
        assert a1 is not None
        assert h2 is not None
        assert s2 is not None
        assert v2 is not None
        assert a2 is not None
        components = _get_color_percentage(h1, s1, v1, a1, h2, s2, v2, a2, percent)
        out.setHsv(*components)
    elif colorspace == QColor.Spec.Hsl:
        h1, s1, l1, a1 = start.getHsl()
        h2, s2, l2, a2 = end.getHsl()
        assert h1 is not None
        assert s1 is not None
        assert l1 is not None
        assert a1 is not None
        assert h2 is not None
        assert s2 is not None
        assert l2 is not None
        assert a2 is not None
        components = _get_color_percentage(h1, s1, l1, a1, h2, s2, l2, a2, percent)
        out.setHsl(*components)
    else:
        raise ValueError("Invalid colorspace!")
    out = out.convertTo(start.spec())
    ensure_valid(out)
    return out


class LibraryPath(enum.Enum):

    """A path to be passed to QLibraryInfo.

    Should mirror QLibraryPath (Qt 5) and QLibraryLocation (Qt 6).
    Values are the respective Qt names.
    """

    prefix = "PrefixPath"
    documentation = "DocumentationPath"
    headers = "HeadersPath"
    libraries = "LibrariesPath"
    library_executables = "LibraryExecutablesPath"
    binaries = "BinariesPath"
    plugins = "PluginsPath"
    qml2_imports = "Qml2ImportsPath"
    arch_data = "ArchDataPath"
    data = "DataPath"
    translations = "TranslationsPath"
    examples = "ExamplesPath"
    tests = "TestsPath"
    settings = "SettingsPath"


def library_path(which: LibraryPath) -> pathlib.Path:
    """Wrapper around QLibraryInfo.path / .location."""
    if machinery.IS_QT6:
        val = getattr(QLibraryInfo.LibraryPath, which.value)
        ret = QLibraryInfo.path(val)
    else:
        # Qt 5
        val = getattr(QLibraryInfo.LibraryLocation, which.value)
        ret = QLibraryInfo.location(val)
    assert ret
    return pathlib.Path(ret)


def extract_enum_val(val: Union[sip.simplewrapper, int, enum.Enum]) -> int:
    """Extract an int value from a Qt enum value.

    For Qt 5, enum values are basically Python integers.
    For Qt 6, they are usually enum.Enum instances, with the value set to the
    integer.
    """
    if isinstance(val, enum.Enum):
        return val.value
    elif isinstance(val, sip.simplewrapper):
        return int(val)  # type: ignore[call-overload]
    return val


def qobj_repr(obj: Optional[QObject]) -> str:
    """Show nicer debug information for a QObject."""
    py_repr = repr(obj)
    if obj is None:
        return py_repr

    try:
        object_name = obj.objectName()
        meta_object = obj.metaObject()
    except AttributeError:
        # Technically not possible if obj is a QObject, but crashing when trying to get
        # some debug info isn't helpful.
        return py_repr

    class_name = "" if meta_object is None else meta_object.className()

    if py_repr.startswith("<") and py_repr.endswith(">"):
        # With a repr such as <QObject object at 0x...>, we want to end up with:
        # <QObject object at 0x..., objectName='...'>
        # But if we have RichRepr() as existing repr, we want:
        # <RichRepr(), objectName='...'>
        py_repr = py_repr[1:-1]

    parts = [py_repr]
    if object_name:
        parts.append(f"objectName={object_name!r}")
    if class_name and f".{class_name} object at 0x" not in py_repr:
        parts.append(f"className={class_name!r}")

    return f"<{', '.join(parts)}>"


_T = TypeVar("_T")


if machinery.IS_QT5:
    # On Qt 5, add/remove Optional where type annotations don't have it.
    # Also we have a special QT_NONE, which (being Any) we can pass to functions
    # where PyQt type hints claim that it's not allowed.

    def remove_optional(obj: Optional[_T]) -> _T:
        return cast(_T, obj)

    def add_optional(obj: _T) -> Optional[_T]:
        return cast(Optional[_T], obj)

    QT_NONE: Any = None
else:
    # On Qt 6, all those things are handled correctly by type annotations, so we
    # have a no-op below.

    def remove_optional(obj: Optional[_T]) -> Optional[_T]:
        return obj

    def add_optional(obj: Optional[_T]) -> Optional[_T]:
        return obj

    QT_NONE: None = None


def maybe_cast(to_type: type[_T], do_cast: bool, value: Any) -> _T:
    """Cast `value` to `to_type` only if `do_cast` is true."""
    if do_cast:
        return cast(
            to_type,  # type: ignore[valid-type]
            value,
        )

    return value
