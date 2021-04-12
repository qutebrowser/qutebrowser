# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Other utilities which don't fit anywhere else."""

import os
import os.path
import io
import re
import sys
import enum
import json
import datetime
import traceback
import functools
import contextlib
import shlex
import mimetypes
from typing import (Any, Callable, IO, Iterator,
                    Optional, Sequence, Tuple, Type, Union,
                    TypeVar, TYPE_CHECKING)
try:
    # Protocol was added in Python 3.8
    from typing import Protocol
except ImportError:  # pragma: no cover
    if not TYPE_CHECKING:
        class Protocol:

            """Empty stub at runtime."""

from PyQt5.QtCore import QUrl, QVersionNumber, QRect
from PyQt5.QtGui import QClipboard, QDesktopServices
from PyQt5.QtWidgets import QApplication

import yaml
try:
    from yaml import (CSafeLoader as YamlLoader,
                      CSafeDumper as YamlDumper)
    YAML_C_EXT = True
except ImportError:  # pragma: no cover
    from yaml import (SafeLoader as YamlLoader,  # type: ignore[misc]
                      SafeDumper as YamlDumper)
    YAML_C_EXT = False

from qutebrowser.utils import log

fake_clipboard = None
log_clipboard = False

is_mac = sys.platform.startswith('darwin')
is_linux = sys.platform.startswith('linux')
is_windows = sys.platform.startswith('win')
is_posix = os.name == 'posix'

_C = TypeVar("_C", bound="Comparable")


class Comparable(Protocol):

    """Protocol for a "comparable" object."""

    def __lt__(self: _C, other: _C) -> bool:
        ...

    def __ge__(self: _C, other: _C) -> bool:
        ...


class VersionNumber:

    """A representation of a version number."""

    def __init__(self, *args: int) -> None:
        self._ver = QVersionNumber(args)  # not *args, to support >3 components
        if self._ver.isNull():
            raise ValueError("Can't construct a null version")

        normalized = self._ver.normalized()
        if normalized != self._ver:
            raise ValueError(
                f"Refusing to construct non-normalized version from {args} "
                f"(normalized: {tuple(normalized.segments())}).")

        self.major = self._ver.majorVersion()
        self.minor = self._ver.minorVersion()
        self.patch = self._ver.microVersion()
        self.segments = self._ver.segments()

    def __str__(self) -> str:
        return ".".join(str(s) for s in self.segments)

    def __repr__(self) -> str:
        args = ", ".join(str(s) for s in self.segments)
        return f'VersionNumber({args})'

    def strip_patch(self) -> 'VersionNumber':
        """Get a new VersionNumber with the patch version removed."""
        return VersionNumber(*self.segments[:2])

    @classmethod
    def parse(cls, s: str) -> 'VersionNumber':
        """Parse a version number from a string."""
        ver, _suffix = QVersionNumber.fromString(s)
        # FIXME: Should we support a suffix?

        if ver.isNull():
            raise ValueError(f"Failed to parse {s}")

        return cls(*ver.normalized().segments())

    def __hash__(self) -> int:
        return hash(self._ver)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionNumber):
            return NotImplemented
        return self._ver == other._ver

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, VersionNumber):
            return NotImplemented
        return self._ver != other._ver

    def __ge__(self, other: 'VersionNumber') -> bool:
        return self._ver >= other._ver  # type: ignore[operator]

    def __gt__(self, other: 'VersionNumber') -> bool:
        return self._ver > other._ver  # type: ignore[operator]

    def __le__(self, other: 'VersionNumber') -> bool:
        return self._ver <= other._ver  # type: ignore[operator]

    def __lt__(self, other: 'VersionNumber') -> bool:
        return self._ver < other._ver  # type: ignore[operator]


class Unreachable(Exception):

    """Raised when there was unreachable code."""


class ClipboardError(Exception):

    """Raised if the clipboard contents are unavailable for some reason."""


class SelectionUnsupportedError(ClipboardError):

    """Raised if [gs]et_clipboard is used and selection=True is unsupported."""

    def __init__(self) -> None:
        super().__init__("Primary selection is not supported on this "
                         "platform!")


class ClipboardEmptyError(ClipboardError):

    """Raised if get_clipboard is used and the clipboard is empty."""


def elide(text: str, length: int) -> str:
    """Elide text so it uses a maximum of length chars."""
    if length < 1:
        raise ValueError("length must be >= 1!")
    if len(text) <= length:
        return text
    else:
        return text[:length - 1] + '\u2026'


def elide_filename(filename: str, length: int) -> str:
    """Elide a filename to the given length.

    The difference to the elide() is that the text is removed from
    the middle instead of from the end. This preserves file name extensions.
    Additionally, standard ASCII dots are used ("...") instead of the unicode
    "…" (U+2026) so it works regardless of the filesystem encoding.

    This function does not handle path separators.

    Args:
        filename: The filename to elide.
        length: The maximum length of the filename, must be at least 3.

    Return:
        The elided filename.
    """
    elidestr = '...'
    if length < len(elidestr):
        raise ValueError('length must be greater or equal to 3')
    if len(filename) <= length:
        return filename
    # Account for '...'
    length -= len(elidestr)
    left = length // 2
    right = length - left
    if right == 0:
        return filename[:left] + elidestr
    else:
        return filename[:left] + elidestr + filename[-right:]


def compact_text(text: str, elidelength: int = None) -> str:
    """Remove leading whitespace and newlines from a text and maybe elide it.

    Args:
        text: The text to compact.
        elidelength: To how many chars to elide.
    """
    lines = []
    for line in text.splitlines():
        lines.append(line.strip())
    out = ''.join(lines)
    if elidelength is not None:
        out = elide(out, elidelength)
    return out


def format_seconds(total_seconds: int) -> str:
    """Format a count of seconds to get a [H:]M:SS string."""
    prefix = '-' if total_seconds < 0 else ''
    hours, rem = divmod(abs(round(total_seconds)), 3600)
    minutes, seconds = divmod(rem, 60)
    chunks = []
    if hours:
        chunks.append(str(hours))
        min_format = '{:02}'
    else:
        min_format = '{}'
    chunks.append(min_format.format(minutes))
    chunks.append('{:02}'.format(seconds))
    return prefix + ':'.join(chunks)


def format_size(size: Optional[float], base: int = 1024, suffix: str = '') -> str:
    """Format a byte size so it's human readable.

    Inspired by https://stackoverflow.com/q/1094841
    """
    prefixes = ['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
    if size is None:
        return '?.??' + suffix
    for p in prefixes:
        if -base < size < base:
            return '{:.02f}{}{}'.format(size, p, suffix)
        size /= base
    return '{:.02f}{}{}'.format(size, prefixes[-1], suffix)


class FakeIOStream(io.TextIOBase):

    """A fake file-like stream which calls a function for write-calls."""

    def __init__(self, write_func: Callable[[str], int]) -> None:
        super().__init__()
        self.write = write_func  # type: ignore[assignment]


@contextlib.contextmanager
def fake_io(write_func: Callable[[str], int]) -> Iterator[None]:
    """Run code with stdout and stderr replaced by FakeIOStreams.

    Args:
        write_func: The function to call when write is called.
    """
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    fake_stderr = FakeIOStream(write_func)
    fake_stdout = FakeIOStream(write_func)
    sys.stderr = fake_stderr  # type: ignore[assignment]
    sys.stdout = fake_stdout  # type: ignore[assignment]
    try:
        yield
    finally:
        # If the code we did run did change sys.stdout/sys.stderr, we leave it
        # unchanged. Otherwise, we reset it.
        if sys.stdout is fake_stdout:  # type: ignore[comparison-overlap]
            sys.stdout = old_stdout
        if sys.stderr is fake_stderr:  # type: ignore[comparison-overlap]
            sys.stderr = old_stderr


@contextlib.contextmanager
def disabled_excepthook() -> Iterator[None]:
    """Run code with the exception hook temporarily disabled."""
    old_excepthook = sys.excepthook
    sys.excepthook = sys.__excepthook__
    try:
        yield
    finally:
        # If the code we did run did change sys.excepthook, we leave it
        # unchanged. Otherwise, we reset it.
        if sys.excepthook is sys.__excepthook__:
            sys.excepthook = old_excepthook


class prevent_exceptions:  # noqa: N801,N806 pylint: disable=invalid-name

    """Decorator to ignore and log exceptions.

    This needs to be used for some places where PyQt segfaults on exceptions or
    silently ignores them.

    We used to re-raise the exception with a single-shot QTimer in a similar
    case, but that lead to a strange problem with a KeyError with some random
    jinja template stuff as content. For now, we only log it, so it doesn't
    pass 100% silently.

    This could also be a function, but as a class (with a "wrong" name) it's
    much cleaner to implement.

    Attributes:
        _retval: The value to return in case of an exception.
        _predicate: The condition which needs to be True to prevent exceptions
    """

    def __init__(self, retval: Any, predicate: bool = True) -> None:
        """Save decorator arguments.

        Gets called on parse-time with the decorator arguments.

        Args:
            See class attributes.
        """
        self._retval = retval
        self._predicate = predicate

    def __call__(self, func: Callable) -> Callable:
        """Called when a function should be decorated.

        Args:
            func: The function to be decorated.

        Return:
            The decorated function.
        """
        if not self._predicate:
            return func

        retval = self._retval

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Call the original function."""
            try:
                return func(*args, **kwargs)
            except BaseException:
                log.misc.exception("Error in {}".format(qualname(func)))
                return retval

        return wrapper


def is_enum(obj: Any) -> bool:
    """Check if a given object is an enum."""
    try:
        return issubclass(obj, enum.Enum)
    except TypeError:
        return False


def pyenum_str(value: enum.Enum) -> str:
    """Get a string representation of a Python enum value.

    This will have the form of "EnumType.membername", which is the default string
    representation for Python up to 3.10. Unfortunately, that changes with Python 3.10:
    https://bugs.python.org/issue40066
    """
    if sys.version_info[:2] >= (3, 10):
        return repr(value)
    return str(value)


def get_repr(obj: Any, constructor: bool = False, **attrs: Any) -> str:
    """Get a suitable __repr__ string for an object.

    Args:
        obj: The object to get a repr for.
        constructor: If True, show the Foo(one=1, two=2) form instead of
                     <Foo one=1 two=2>.
        attrs: The attributes to add.
    """
    cls = qualname(obj.__class__)
    parts = []
    items = sorted(attrs.items())

    for name, val in items:
        if isinstance(val, enum.Enum):
            s = pyenum_str(val)
        else:
            s = repr(val)
        parts.append(f'{name}={s}')

    if constructor:
        return '{}({})'.format(cls, ', '.join(parts))
    else:
        if parts:
            return '<{} {}>'.format(cls, ' '.join(parts))
        else:
            return '<{}>'.format(cls)


def qualname(obj: Any) -> str:
    """Get the fully qualified name of an object.

    Based on twisted.python.reflect.fullyQualifiedName.

    Should work with:
        - functools.partial objects
        - functions
        - classes
        - methods
        - modules
    """
    if isinstance(obj, functools.partial):
        obj = obj.func

    if hasattr(obj, '__module__'):
        prefix = '{}.'.format(obj.__module__)
    else:
        prefix = ''

    if hasattr(obj, '__qualname__'):
        return '{}{}'.format(prefix, obj.__qualname__)
    elif hasattr(obj, '__name__'):
        return '{}{}'.format(prefix, obj.__name__)
    else:
        return repr(obj)


_ExceptionType = Union[Type[BaseException], Tuple[Type[BaseException]]]


def raises(exc: _ExceptionType, func: Callable, *args: Any) -> bool:
    """Check if a function raises a given exception.

    Args:
        exc: A single exception or an iterable of exceptions.
        func: A function to call.
        *args: The arguments to pass to the function.

    Returns:
        True if the exception was raised, False otherwise.
    """
    try:
        func(*args)
    except exc:
        return True
    else:
        return False


def force_encoding(text: str, encoding: str) -> str:
    """Make sure a given text is encodable with the given encoding.

    This replaces all chars not encodable with question marks.
    """
    return text.encode(encoding, errors='replace').decode(encoding)


def sanitize_filename(name: str,
                      replacement: Optional[str] = '_',
                      shorten: bool = False) -> str:
    """Replace invalid filename characters.

    Note: This should be used for the basename, as it also removes the path
    separator.

    Args:
        name: The filename.
        replacement: The replacement character (or None).
        shorten: Shorten the filename if it's too long for the filesystem.
    """
    if replacement is None:
        replacement = ''

    # Remove chars which can't be encoded in the filename encoding.
    # See https://github.com/qutebrowser/qutebrowser/issues/427
    encoding = sys.getfilesystemencoding()
    name = force_encoding(name, encoding)

    # See also
    # https://en.wikipedia.org/wiki/Filename#Reserved_characters_and_words
    if is_windows:
        bad_chars = '\\/:*?"<>|'
    elif is_mac:
        # Colons can be confusing in finder https://superuser.com/a/326627
        bad_chars = '/:'
    else:
        bad_chars = '/'

    for bad_char in bad_chars:
        name = name.replace(bad_char, replacement)

    if not shorten:
        return name

    # Truncate the filename if it's too long.
    # Most filesystems have a maximum filename length of 255 bytes:
    # https://en.wikipedia.org/wiki/Comparison_of_file_systems#Limits
    # We also want to keep some space for QtWebEngine's ".download" suffix, as
    # well as deduplication counters.
    max_bytes = 255 - len("(123).download")
    root, ext = os.path.splitext(name)
    root = root[:max_bytes - len(ext)]
    excess = len(os.fsencode(root + ext)) - max_bytes

    while excess > 0 and root:
        # Max 4 bytes per character is assumed.
        # Integer division floors to -∞, not to 0.
        root = root[:(-excess // 4)]
        excess = len(os.fsencode(root + ext)) - max_bytes

    if not root:
        # Trimming the root is not enough. We must trim the extension.
        # We leave one character in the root, so that the filename
        # doesn't start with a dot, which makes the file hidden.
        root = name[0]
        excess = len(os.fsencode(root + ext)) - max_bytes
        while excess > 0 and ext:
            ext = ext[:(-excess // 4)]
            excess = len(os.fsencode(root + ext)) - max_bytes

        assert ext, name

    name = root + ext

    return name


def set_clipboard(data: str, selection: bool = False) -> None:
    """Set the clipboard to some given data."""
    global fake_clipboard
    if selection and not supports_selection():
        raise SelectionUnsupportedError
    if log_clipboard:
        what = 'primary selection' if selection else 'clipboard'
        log.misc.debug("Setting fake {}: {}".format(what, json.dumps(data)))
        fake_clipboard = data
    else:
        mode = QClipboard.Selection if selection else QClipboard.Clipboard
        QApplication.clipboard().setText(data, mode=mode)


def get_clipboard(selection: bool = False, fallback: bool = False) -> str:
    """Get data from the clipboard.

    Args:
        selection: Use the primary selection.
        fallback: Fall back to the clipboard if primary selection is
                  unavailable.
    """
    global fake_clipboard
    if fallback and not selection:
        raise ValueError("fallback given without selection!")

    if selection and not supports_selection():
        if fallback:
            selection = False
        else:
            raise SelectionUnsupportedError

    if fake_clipboard is not None:
        data = fake_clipboard
        fake_clipboard = None
    else:
        mode = QClipboard.Selection if selection else QClipboard.Clipboard
        data = QApplication.clipboard().text(mode=mode)

    target = "Primary selection" if selection else "Clipboard"
    if not data.strip():
        raise ClipboardEmptyError("{} is empty.".format(target))
    log.misc.debug("{} contained: {!r}".format(target, data))

    return data


def supports_selection() -> bool:
    """Check if the OS supports primary selection."""
    return QApplication.clipboard().supportsSelection()


def open_file(filename: str, cmdline: str = None) -> None:
    """Open the given file.

    If cmdline is not given, downloads.open_dispatcher is used.
    If open_dispatcher is unset, the system's default application is used.

    Args:
        filename: The filename to open.
        cmdline: The command to use as string. A `{}` is expanded to the
                 filename. None means to use the system's default application
                 or `downloads.open_dispatcher` if set. If no `{}` is found,
                 the filename is appended to the cmdline.
    """
    # Import late to avoid circular imports:
    # - usertypes -> utils -> guiprocess -> message -> usertypes
    # - usertypes -> utils -> config -> configdata -> configtypes ->
    #   cmdutils -> command -> message -> usertypes
    from qutebrowser.config import config
    from qutebrowser.misc import guiprocess
    from qutebrowser.utils import version, message

    # the default program to open downloads with - will be empty string
    # if we want to use the default
    override = config.val.downloads.open_dispatcher

    if version.is_flatpak():
        if cmdline:
            message.error("Cannot spawn download dispatcher from sandbox")
            return
        if override:
            message.warning("Ignoring download dispatcher from config in "
                            "sandbox environment")
            override = None

    # precedence order: cmdline > downloads.open_dispatcher > openUrl

    if cmdline is None and not override:
        log.misc.debug("Opening {} with the system application"
                       .format(filename))
        url = QUrl.fromLocalFile(filename)
        QDesktopServices.openUrl(url)
        return

    if cmdline is None and override:
        cmdline = override

    assert cmdline is not None

    cmd, *args = shlex.split(cmdline)
    args = [arg.replace('{}', filename) for arg in args]
    if '{}' not in cmdline:
        args.append(filename)
    log.misc.debug("Opening {} with {}"
                   .format(filename, [cmd] + args))
    proc = guiprocess.GUIProcess(what='open-file')
    proc.start_detached(cmd, args)


def unused(_arg: Any) -> None:
    """Function which does nothing to avoid pylint complaining."""


def expand_windows_drive(path: str) -> str:
    r"""Expand a drive-path like E: into E:\.

    Does nothing for other paths.

    Args:
        path: The path to expand.
    """
    # Usually, "E:" on Windows refers to the current working directory on drive
    # E:\. The correct way to specifify drive E: is "E:\", but most users
    # probably don't use the "multiple working directories" feature and expect
    # "E:" and "E:\" to be equal.
    if re.fullmatch(r'[A-Z]:', path, re.IGNORECASE):
        return path + "\\"
    else:
        return path


def yaml_load(f: Union[str, IO[str]]) -> Any:
    """Wrapper over yaml.load using the C loader if possible."""
    start = datetime.datetime.now()

    # WORKAROUND for https://github.com/yaml/pyyaml/pull/181
    with log.py_warning_filter(
            category=DeprecationWarning,
            message=r"Using or importing the ABCs from 'collections' instead "
            r"of from 'collections\.abc' is deprecated.*"):
        try:
            data = yaml.load(f, Loader=YamlLoader)
        except ValueError as e:
            if str(e).startswith('could not convert string to float'):
                # WORKAROUND for https://github.com/yaml/pyyaml/issues/168
                raise yaml.YAMLError(e)
            raise  # pragma: no cover

    end = datetime.datetime.now()

    delta = (end - start).total_seconds()
    deadline = 10 if 'CI' in os.environ else 2
    if delta > deadline:  # pragma: no cover
        log.misc.warning(
            "YAML load took unusually long, please report this at "
            "https://github.com/qutebrowser/qutebrowser/issues/2777\n"
            "duration: {}s\n"
            "PyYAML version: {}\n"
            "C extension: {}\n"
            "Stack:\n\n"
            "{}".format(
                delta, yaml.__version__, YAML_C_EXT,
                ''.join(traceback.format_stack())))

    return data


def yaml_dump(data: Any, f: IO[str] = None) -> Optional[str]:
    """Wrapper over yaml.dump using the C dumper if possible.

    Also returns a str instead of bytes.
    """
    yaml_data = yaml.dump(data, f, Dumper=YamlDumper, default_flow_style=False,
                          encoding='utf-8', allow_unicode=True)
    if yaml_data is None:
        return None
    else:
        return yaml_data.decode('utf-8')


def chunk(elems: Sequence, n: int) -> Iterator[Sequence]:
    """Yield successive n-sized chunks from elems.

    If elems % n != 0, the last chunk will be smaller.
    """
    if n < 1:
        raise ValueError("n needs to be at least 1!")
    for i in range(0, len(elems), n):
        yield elems[i:i + n]


def guess_mimetype(filename: str, fallback: bool = False) -> str:
    """Guess a mimetype based on a filename.

    Args:
        filename: The filename to check.
        fallback: Fall back to application/octet-stream if unknown.
    """
    mimetype, _encoding = mimetypes.guess_type(filename)
    if mimetype is None:
        if fallback:
            return 'application/octet-stream'
        else:
            raise ValueError("Got None mimetype for {}".format(filename))
    return mimetype


def ceil_log(number: int, base: int) -> int:
    """Compute max(1, ceil(log(number, base))).

    Use only integer arithmetic in order to avoid numerical error.
    """
    if number < 1 or base < 2:
        raise ValueError("math domain error")
    result = 1
    accum = base
    while accum < number:
        result += 1
        accum *= base
    return result


def parse_duration(duration: str) -> int:
    """Parse duration in format XhYmZs into milliseconds duration."""
    if duration.isdigit():
        # For backward compatibility return milliseconds
        return int(duration)

    match = re.fullmatch(
        r'(?P<hours>[0-9]+(\.[0-9])?h)?\s*'
        r'(?P<minutes>[0-9]+(\.[0-9])?m)?\s*'
        r'(?P<seconds>[0-9]+(\.[0-9])?s)?',
        duration
    )
    if not match or not match.group(0):
        raise ValueError(
            f"Invalid duration: {duration} - "
            "expected XhYmZs or a number of milliseconds"
        )
    seconds_string = match.group('seconds') if match.group('seconds') else '0'
    seconds = float(seconds_string.rstrip('s'))
    minutes_string = match.group('minutes') if match.group('minutes') else '0'
    minutes = float(minutes_string.rstrip('m'))
    hours_string = match.group('hours') if match.group('hours') else '0'
    hours = float(hours_string.rstrip('h'))
    milliseconds = int((seconds + minutes * 60 + hours * 3600) * 1000)
    return milliseconds


def mimetype_extension(mimetype: str) -> Optional[str]:
    """Get a suitable extension for a given mimetype.

    This mostly delegates to Python's mimetypes.guess_extension(), but backports some
    changes (via a simple override dict) which are missing from earlier Python versions.
    Most likely, this can be dropped once the minimum Python version is raised to 3.7.
    """
    overrides = {
        # Added around 3.8
        "application/manifest+json": ".webmanifest",
        "application/x-hdf5": ".h5",

        # Added in Python 3.7
        "application/wasm": ".wasm",

        # Wrong values for Python 3.6
        # https://bugs.python.org/issue1043134
        # https://github.com/python/cpython/pull/14375
        "application/octet-stream": ".bin",  # not .a
        "application/postscript": ".ps",  # not .ai
        "application/vnd.ms-excel": ".xls",  # not .xlb
        "application/vnd.ms-powerpoint": ".ppt",  # not .pot
        "application/xml": ".xsl",  # not .rdf
        "audio/mpeg": ".mp3",  # not .mp2
        "image/jpeg": ".jpg",  # not .jpe
        "image/tiff": ".tiff",  # not .tif
        "text/html": ".html",  # not .htm
        "text/plain": ".txt",  # not .bat
        "video/mpeg": ".mpeg",  # not .m1v
    }
    if mimetype in overrides:
        return overrides[mimetype]
    return mimetypes.guess_extension(mimetype, strict=False)


@contextlib.contextmanager
def cleanup_file(filepath: str) -> Iterator[None]:
    """Context that deletes a file upon exit or error.

    Args:
        filepath: The file path
    """
    try:
        yield
    finally:
        try:
            os.remove(filepath)
        except OSError as e:
            log.misc.error(f"Failed to delete tempfile {filepath} ({e})!")


_RECT_PATTERN = re.compile(r'(?P<w>\d+)x(?P<h>\d+)\+(?P<x>\d+)\+(?P<y>\d+)')


def parse_rect(s: str) -> QRect:
    """Parse a rectangle string like 20x20+5+3.

    Negative offsets aren't supported, and neither is leaving off parts of the string.
    """
    match = _RECT_PATTERN.match(s)
    if not match:
        raise ValueError(f"String {s} does not match WxH+X+Y")

    w = int(match.group('w'))
    h = int(match.group('h'))
    x = int(match.group('x'))
    y = int(match.group('y'))

    try:
        rect = QRect(x, y, w, h)
    except OverflowError as e:
        raise ValueError(e)

    if not rect.isValid():
        raise ValueError("Invalid rectangle")

    return rect
