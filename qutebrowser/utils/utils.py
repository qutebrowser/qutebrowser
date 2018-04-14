# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import socket
import shlex
import glob

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QColor, QClipboard, QDesktopServices
from PyQt5.QtWidgets import QApplication
import pkg_resources
import yaml
try:
    from yaml import CSafeLoader as YamlLoader, CSafeDumper as YamlDumper
    YAML_C_EXT = True
except ImportError:  # pragma: no cover
    from yaml import SafeLoader as YamlLoader, SafeDumper as YamlDumper
    YAML_C_EXT = False

import qutebrowser
from qutebrowser.utils import qtutils, log


fake_clipboard = None
log_clipboard = False
_resource_cache = {}

is_mac = sys.platform.startswith('darwin')
is_linux = sys.platform.startswith('linux')
is_windows = sys.platform.startswith('win')
is_posix = os.name == 'posix'


class Unreachable(Exception):

    """Raised when there was unreachable code."""


class ClipboardError(Exception):

    """Raised if the clipboard contents are unavailable for some reason."""


class SelectionUnsupportedError(ClipboardError):

    """Raised if [gs]et_clipboard is used and selection=True is unsupported."""

    def __init__(self):
        super().__init__("Primary selection is not supported on this "
                         "platform!")


class ClipboardEmptyError(ClipboardError):

    """Raised if get_clipboard is used and the clipboard is empty."""


def elide(text, length):
    """Elide text so it uses a maximum of length chars."""
    if length < 1:
        raise ValueError("length must be >= 1!")
    if len(text) <= length:
        return text
    else:
        return text[:length - 1] + '\u2026'


def elide_filename(filename, length):
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


def compact_text(text, elidelength=None):
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


def preload_resources():
    """Load resource files into the cache."""
    for subdir, pattern in [('html', '*.html'), ('javascript', '*.js')]:
        path = resource_filename(subdir)
        for full_path in glob.glob(os.path.join(path, pattern)):
            sub_path = '/'.join([subdir, os.path.basename(full_path)])
            _resource_cache[sub_path] = read_file(sub_path)


def read_file(filename, binary=False):
    """Get the contents of a file contained with qutebrowser.

    Args:
        filename: The filename to open as string.
        binary: Whether to return a binary string.
                If False, the data is UTF-8-decoded.

    Return:
        The file contents as string.
    """
    if not binary and filename in _resource_cache:
        return _resource_cache[filename]

    if hasattr(sys, 'frozen'):
        # PyInstaller doesn't support pkg_resources :(
        # https://github.com/pyinstaller/pyinstaller/wiki/FAQ#misc
        fn = os.path.join(os.path.dirname(sys.executable), filename)
        if binary:
            with open(fn, 'rb') as f:
                return f.read()
        else:
            with open(fn, 'r', encoding='utf-8') as f:
                return f.read()
    else:
        data = pkg_resources.resource_string(qutebrowser.__name__, filename)
        if not binary:
            data = data.decode('UTF-8')
        return data


def resource_filename(filename):
    """Get the absolute filename of a file contained with qutebrowser.

    Args:
        filename: The filename.

    Return:
        The absolute filename.
    """
    if hasattr(sys, 'frozen'):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return pkg_resources.resource_filename(qutebrowser.__name__, filename)


def _get_color_percentage(a_c1, a_c2, a_c3, b_c1, b_c2, b_c3, percent):
    """Get a color which is percent% interpolated between start and end.

    Args:
        a_c1, a_c2, a_c3: Start color components (R, G, B / H, S, V / H, S, L)
        b_c1, b_c2, b_c3: End color components (R, G, B / H, S, V / H, S, L)
        percent: Percentage to interpolate, 0-100.
                 0: Start color will be returned.
                 100: End color will be returned.

    Return:
        A (c1, c2, c3) tuple with the interpolated color components.
    """
    if not 0 <= percent <= 100:
        raise ValueError("percent needs to be between 0 and 100!")
    out_c1 = round(a_c1 + (b_c1 - a_c1) * percent / 100)
    out_c2 = round(a_c2 + (b_c2 - a_c2) * percent / 100)
    out_c3 = round(a_c3 + (b_c3 - a_c3) * percent / 100)
    return (out_c1, out_c2, out_c3)


def interpolate_color(start, end, percent, colorspace=QColor.Rgb):
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
    qtutils.ensure_valid(start)
    qtutils.ensure_valid(end)

    if colorspace is None:
        if percent == 100:
            return QColor(*end.getRgb())
        else:
            return QColor(*start.getRgb())

    out = QColor()
    if colorspace == QColor.Rgb:
        a_c1, a_c2, a_c3, _alpha = start.getRgb()
        b_c1, b_c2, b_c3, _alpha = end.getRgb()
        components = _get_color_percentage(a_c1, a_c2, a_c3, b_c1, b_c2, b_c3,
                                           percent)
        out.setRgb(*components)
    elif colorspace == QColor.Hsv:
        a_c1, a_c2, a_c3, _alpha = start.getHsv()
        b_c1, b_c2, b_c3, _alpha = end.getHsv()
        components = _get_color_percentage(a_c1, a_c2, a_c3, b_c1, b_c2, b_c3,
                                           percent)
        out.setHsv(*components)
    elif colorspace == QColor.Hsl:
        a_c1, a_c2, a_c3, _alpha = start.getHsl()
        b_c1, b_c2, b_c3, _alpha = end.getHsl()
        components = _get_color_percentage(a_c1, a_c2, a_c3, b_c1, b_c2, b_c3,
                                           percent)
        out.setHsl(*components)
    else:
        raise ValueError("Invalid colorspace!")
    out = out.convertTo(start.spec())
    qtutils.ensure_valid(out)
    return out


def format_seconds(total_seconds):
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


def format_size(size, base=1024, suffix=''):
    """Format a byte size so it's human readable.

    Inspired by http://stackoverflow.com/q/1094841
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

    def __init__(self, write_func):
        super().__init__()
        self.write = write_func


@contextlib.contextmanager
def fake_io(write_func):
    """Run code with stdout and stderr replaced by FakeIOStreams.

    Args:
        write_func: The function to call when write is called.
    """
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    fake_stderr = FakeIOStream(write_func)
    fake_stdout = FakeIOStream(write_func)
    sys.stderr = fake_stderr
    sys.stdout = fake_stdout
    try:
        yield
    finally:
        # If the code we did run did change sys.stdout/sys.stderr, we leave it
        # unchanged. Otherwise, we reset it.
        if sys.stdout is fake_stdout:
            sys.stdout = old_stdout
        if sys.stderr is fake_stderr:
            sys.stderr = old_stderr


@contextlib.contextmanager
def disabled_excepthook():
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

    def __init__(self, retval, predicate=True):
        """Save decorator arguments.

        Gets called on parse-time with the decorator arguments.

        Args:
            See class attributes.
        """
        self._retval = retval
        self._predicate = predicate

    def __call__(self, func):
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
        def wrapper(*args, **kwargs):
            """Call the original function."""
            try:
                return func(*args, **kwargs)
            except BaseException:
                log.misc.exception("Error in {}".format(qualname(func)))
                return retval

        return wrapper


def is_enum(obj):
    """Check if a given object is an enum."""
    try:
        return issubclass(obj, enum.Enum)
    except TypeError:
        return False


def get_repr(obj, constructor=False, **attrs):
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
        parts.append('{}={!r}'.format(name, val))
    if constructor:
        return '{}({})'.format(cls, ', '.join(parts))
    else:
        if parts:
            return '<{} {}>'.format(cls, ' '.join(parts))
        else:
            return '<{}>'.format(cls)


def qualname(obj):
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


def raises(exc, func, *args):
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


def force_encoding(text, encoding):
    """Make sure a given text is encodable with the given encoding.

    This replaces all chars not encodable with question marks.
    """
    return text.encode(encoding, errors='replace').decode(encoding)


def sanitize_filename(name, replacement='_'):
    """Replace invalid filename characters.

    Note: This should be used for the basename, as it also removes the path
    separator.

    Args:
        name: The filename.
        replacement: The replacement character (or None).
    """
    if replacement is None:
        replacement = ''
    # Bad characters taken from Windows, there are even fewer on Linux
    # See also
    # https://en.wikipedia.org/wiki/Filename#Reserved_characters_and_words
    bad_chars = '\\/:*?"<>|'
    for bad_char in bad_chars:
        name = name.replace(bad_char, replacement)
    return name


def set_clipboard(data, selection=False):
    """Set the clipboard to some given data."""
    if selection and not supports_selection():
        raise SelectionUnsupportedError
    if log_clipboard:
        what = 'primary selection' if selection else 'clipboard'
        log.misc.debug("Setting fake {}: {}".format(what, json.dumps(data)))
    else:
        mode = QClipboard.Selection if selection else QClipboard.Clipboard
        QApplication.clipboard().setText(data, mode=mode)


def get_clipboard(selection=False, fallback=False):
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


def supports_selection():
    """Check if the OS supports primary selection."""
    return QApplication.clipboard().supportsSelection()


def random_port():
    """Get a random free port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def open_file(filename, cmdline=None):
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

    # the default program to open downloads with - will be empty string
    # if we want to use the default
    override = config.val.downloads.open_dispatcher

    # precedence order: cmdline > downloads.open_dispatcher > openUrl

    if cmdline is None and not override:
        log.misc.debug("Opening {} with the system application"
                       .format(filename))
        url = QUrl.fromLocalFile(filename)
        QDesktopServices.openUrl(url)
        return

    if cmdline is None and override:
        cmdline = override

    cmd, *args = shlex.split(cmdline)
    args = [arg.replace('{}', filename) for arg in args]
    if '{}' not in cmdline:
        args.append(filename)
    log.misc.debug("Opening {} with {}"
                   .format(filename, [cmd] + args))
    proc = guiprocess.GUIProcess(what='open-file')
    proc.start_detached(cmd, args)


def unused(_arg):
    """Function which does nothing to avoid pylint complaining."""
    pass


def expand_windows_drive(path):
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


def yaml_load(f):
    """Wrapper over yaml.load using the C loader if possible."""
    start = datetime.datetime.now()
    data = yaml.load(f, Loader=YamlLoader)
    end = datetime.datetime.now()

    delta = (end - start).total_seconds()
    deadline = 5 if 'CI' in os.environ else 2
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


def yaml_dump(data, f=None):
    """Wrapper over yaml.dump using the C dumper if possible.

    Also returns a str instead of bytes.
    """
    yaml_data = yaml.dump(data, f, Dumper=YamlDumper, default_flow_style=False,
                          encoding='utf-8', allow_unicode=True)
    if yaml_data is None:
        return None
    else:
        return yaml_data.decode('utf-8')


def chunk(elems, n):
    """Yield successive n-sized chunks from elems.

    If elems % n != 0, the last chunk will be smaller.
    """
    if n < 1:
        raise ValueError("n needs to be at least 1!")
    for i in range(0, len(elems), n):
        yield elems[i:i + n]
