# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import io
import sys
import enum
import inspect
import os.path
import collections
import functools
import contextlib
import itertools

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence, QColor
import pkg_resources

import qutebrowser
from qutebrowser.utils import qtutils, log


def elide(text, length):
    """Elide text so it uses a maximum of length chars."""
    if length < 1:
        raise ValueError("length must be >= 1!")
    if len(text) <= length:
        return text
    else:
        return text[:length - 1] + '\u2026'


def compact_text(text, elidelength=None):
    """Remove leading whitespace and newlines from a text and maybe elide it.

    Args:
        text: The text to compact.
        elidelength: To how many chars to elide.
    """
    out = []
    for line in text.splitlines():
        out.append(line.strip())
    out = ''.join(out)
    if elidelength is not None:
        out = elide(out, elidelength)
    return out


def read_file(filename, binary=False):
    """Get the contents of a file contained with qutebrowser.

    Args:
        filename: The filename to open as string.
        binary: Whether to return a binary string.
                If False, the data is UTF-8-decoded.

    Return:
        The file contents as string.
    """
    if hasattr(sys, 'frozen'):
        # cx_Freeze doesn't support pkg_resources :(
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


def actute_warning():
    """Display a warning about the dead_actute issue if needed."""
    # WORKAROUND (remove this when we bump the requirements to 5.3.0)
    # Non Linux OS' aren't affected
    if not sys.platform.startswith('linux'):
        return
    # If no compose file exists for some reason, we're not affected
    if not os.path.exists('/usr/share/X11/locale/en_US.UTF-8/Compose'):
        return
    # Qt >= 5.3 doesn't seem to be affected
    try:
        if qtutils.version_check('5.3.0'):
            return
    except ValueError:  # pragma: no cover
        pass
    try:
        with open('/usr/share/X11/locale/en_US.UTF-8/Compose', 'r',
                  encoding='utf-8') as f:
            for line in f:  # pragma: no branch
                if '<dead_actute>' in line:
                    if sys.stdout is not None:
                        sys.stdout.flush()
                    print("Note: If you got a 'dead_actute' warning above, "
                          "that is not a bug in qutebrowser! See "
                          "https://bugs.freedesktop.org/show_bug.cgi?id=69476 "
                          "for details.")
                    break  # pragma: no branch
    except OSError:
        log.init.exception("Failed to read Compose file")


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

    Return:
        The interpolated QColor, with the same spec as the given start color.
    """
    qtutils.ensure_valid(start)
    qtutils.ensure_valid(end)
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


def format_timedelta(td):
    """Format a timedelta to get a "1h 5m 1s" string."""
    prefix = '-' if td.total_seconds() < 0 else ''
    hours, rem = divmod(abs(round(td.total_seconds())), 3600)
    minutes, seconds = divmod(rem, 60)
    chunks = []
    if hours:
        chunks.append('{}h'.format(hours))
    if minutes:
        chunks.append('{}m'.format(minutes))
    if seconds or not chunks:
        chunks.append('{}s'.format(seconds))
    return prefix + ' '.join(chunks)


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


def key_to_string(key):
    """Convert a Qt::Key member to a meaningful name.

    Args:
        key: A Qt::Key member.

    Return:
        A name of the key as a string.
    """
    special_names_str = {
        # Some keys handled in a weird way by QKeySequence::toString.
        # See https://bugreports.qt.io/browse/QTBUG-40030
        # Most are unlikely to be ever needed, but you never know ;)
        # For dead/combining keys, we return the corresponding non-combining
        # key, as that's easier to add to the config.
        'Key_Blue': 'Blue',
        'Key_Calendar': 'Calendar',
        'Key_ChannelDown': 'Channel Down',
        'Key_ChannelUp': 'Channel Up',
        'Key_ContrastAdjust': 'Contrast Adjust',
        'Key_Dead_Abovedot': '˙',
        'Key_Dead_Abovering': '˚',
        'Key_Dead_Acute': '´',
        'Key_Dead_Belowdot': 'Belowdot',
        'Key_Dead_Breve': '˘',
        'Key_Dead_Caron': 'ˇ',
        'Key_Dead_Cedilla': '¸',
        'Key_Dead_Circumflex': '^',
        'Key_Dead_Diaeresis': '¨',
        'Key_Dead_Doubleacute': '˝',
        'Key_Dead_Grave': '`',
        'Key_Dead_Hook': 'Hook',
        'Key_Dead_Horn': 'Horn',
        'Key_Dead_Iota': 'Iota',
        'Key_Dead_Macron': '¯',
        'Key_Dead_Ogonek': '˛',
        'Key_Dead_Semivoiced_Sound': 'Semivoiced Sound',
        'Key_Dead_Tilde': '~',
        'Key_Dead_Voiced_Sound': 'Voiced Sound',
        'Key_Exit': 'Exit',
        'Key_Green': 'Green',
        'Key_Guide': 'Guide',
        'Key_Info': 'Info',
        'Key_LaunchG': 'LaunchG',
        'Key_LaunchH': 'LaunchH',
        'Key_MediaLast': 'MediaLast',
        'Key_Memo': 'Memo',
        'Key_MicMute': 'Mic Mute',
        'Key_Mode_switch': 'Mode switch',
        'Key_Multi_key': 'Multi key',
        'Key_PowerDown': 'Power Down',
        'Key_Red': 'Red',
        'Key_Settings': 'Settings',
        'Key_SingleCandidate': 'Single Candidate',
        'Key_ToDoList': 'Todo List',
        'Key_TouchpadOff': 'Touchpad Off',
        'Key_TouchpadOn': 'Touchpad On',
        'Key_TouchpadToggle': 'Touchpad toggle',
        'Key_Yellow': 'Yellow',
        'Key_Alt': 'Alt',
        'Key_AltGr': 'AltGr',
        'Key_Control': 'Control',
        'Key_Direction_L': 'Direction L',
        'Key_Direction_R': 'Direction R',
        'Key_Hyper_L': 'Hyper L',
        'Key_Hyper_R': 'Hyper R',
        'Key_Meta': 'Meta',
        'Key_Shift': 'Shift',
        'Key_Super_L': 'Super L',
        'Key_Super_R': 'Super R',
        'Key_unknown': 'Unknown',
    }
    # We now build our real special_names dict from the string mapping above.
    # The reason we don't do this directly is that certain Qt versions don't
    # have all the keys, so we want to ignore AttributeErrors.
    special_names = {}
    for k, v in special_names_str.items():
        try:
            special_names[getattr(Qt, k)] = v
        except AttributeError:
            pass
    # Now we check if the key is any special one - if not, we use
    # QKeySequence::toString.
    try:
        return special_names[key]
    except KeyError:
        name = QKeySequence(key).toString()
        morphings = {
            'Backtab': 'Tab',
            'Esc': 'Escape',
        }
        if name in morphings:
            return morphings[name]
        else:
            return name


def keyevent_to_string(e):
    """Convert a QKeyEvent to a meaningful name.

    Args:
        e: A QKeyEvent.

    Return:
        A name of the key (combination) as a string or
        None if only modifiers are pressed..
    """
    if sys.platform == 'darwin':
        # Qt swaps Ctrl/Meta on OS X, so we switch it back here so the user can
        # use it in the config as expected. See:
        # https://github.com/The-Compiler/qutebrowser/issues/110
        # http://doc.qt.io/qt-5.4/osx-issues.html#special-keys
        modmask2str = collections.OrderedDict([
            (Qt.MetaModifier, 'Ctrl'),
            (Qt.AltModifier, 'Alt'),
            (Qt.ControlModifier, 'Meta'),
            (Qt.ShiftModifier, 'Shift'),
        ])
    else:
        modmask2str = collections.OrderedDict([
            (Qt.ControlModifier, 'Ctrl'),
            (Qt.AltModifier, 'Alt'),
            (Qt.MetaModifier, 'Meta'),
            (Qt.ShiftModifier, 'Shift'),
        ])
    modifiers = (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta,
                 Qt.Key_AltGr, Qt.Key_Super_L, Qt.Key_Super_R,
                 Qt.Key_Hyper_L, Qt.Key_Hyper_R, Qt.Key_Direction_L,
                 Qt.Key_Direction_R)
    if e.key() in modifiers:
        # Only modifier pressed
        return None
    mod = e.modifiers()
    parts = []
    for (mask, s) in modmask2str.items():
        if mod & mask and s not in parts:
            parts.append(s)
    parts.append(key_to_string(e.key()))
    return '+'.join(parts)


def normalize_keystr(keystr):
    """Normalize a keystring like Ctrl-Q to a keystring like Ctrl+Q.

    Args:
        keystr: The key combination as a string.

    Return:
        The normalized keystring.
    """
    keystr = keystr.lower()
    replacements = (
        ('control', 'ctrl'),
        ('windows', 'meta'),
        ('mod1', 'alt'),
        ('mod4', 'meta'),
    )
    for (orig, repl) in replacements:
        keystr = keystr.replace(orig, repl)
    for mod in ('ctrl', 'meta', 'alt', 'shift'):
        keystr = keystr.replace(mod + '-', mod + '+')
    return keystr


class FakeIOStream(io.TextIOBase):

    """A fake file-like stream which calls a function for write-calls."""

    def __init__(self, write_func):
        self.write = write_func

    def flush(self):
        """Override flush() to satisfy pylint."""
        return super().flush()

    def isatty(self):
        """Override isatty() to satisfy pylint."""
        return super().isatty()


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


class prevent_exceptions:  # pylint: disable=invalid-name

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
        def wrapper(*args, **kwargs):  # pylint: disable=missing-docstring
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
    if hasattr(obj, '__qualname__'):
        name = obj.__qualname__
    elif hasattr(obj, '__name__'):
        name = obj.__name__
    else:
        name = repr(obj)

    if inspect.isclass(obj) or inspect.isfunction(obj):
        module = obj.__module__
        return "{}.{}".format(module, name)
    elif inspect.ismethod(obj):
        return "{}.{}".format(obj.__module__, name)
    else:
        return name


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


def newest_slice(iterable, count):
    """Get an iterable for the n newest items of the given iterable.

    Args:
        count: How many elements to get.
               0: get no items:
               n: get the n newest items
              -1: get all items
    """
    if count < -1:
        raise ValueError("count can't be smaller than -1!")
    elif count == 0:
        return []
    elif count == -1 or len(iterable) < count:
        return iterable
    else:
        return itertools.islice(iterable, len(iterable) - count, len(iterable))
