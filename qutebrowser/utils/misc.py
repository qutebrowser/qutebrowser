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

"""Other utilities which don't fit anywhere else.

Module attributes:
    MAXVAL: A dictionary of C/Qt types (as string) mapped to their maximum
            value.
"""

import os
import re
import sys
import shlex
import email
import email.policy
import os.path
import operator
import urllib.request
from urllib.parse import urljoin, urlencode
from functools import reduce

from distutils.version import StrictVersion as Version
from PyQt5.QtCore import QCoreApplication, QStandardPaths, QEventLoop, qVersion
from PyQt5.QtGui import QColor
from pkg_resources import resource_string

import qutebrowser


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


def elide(text, length):
    """Elide text so it uses a maximum of length chars."""
    if length < 1:
        raise ValueError("length must be >= 1!")
    if len(text) <= length:
        return text
    else:
        return text[:length - 1] + '\u2026'


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


def read_file(filename):
    """Get the contents of a file contained with qutebrowser.

    Args:
        filename: The filename to open as string.

    Return:
        The file contents as string.
    """
    if hasattr(sys, 'frozen'):
        # cx_Freeze doesn't support pkg_resources :(
        fn = os.path.join(os.path.dirname(sys.executable), filename)
        with open(fn, 'r', encoding='UTF-8') as f:
            return f.read()
    else:
        return resource_string(qutebrowser.__name__, filename).decode('UTF-8')


def dotted_getattr(obj, path):
    """getattr supporting the dot notation.

    Args:
        obj: The object where to start.
        path: A dotted object path as a string.

    Return:
        The object at path.
    """
    return reduce(getattr, path.split('.'), obj)


def safe_shlex_split(s):
    r"""Split a string via shlex safely (don't bail out on unbalanced quotes).

    We split while the user is typing (for completion), and as
    soon as " or \ is typed, the string is invalid for shlex,
    because it encounters EOF while in quote/escape state.

    Here we fix this error temporarely so shlex doesn't blow up,
    and then retry splitting again.

    Since shlex raises ValueError in both cases we unfortunately
    have to parse the exception string...
    """
    while True:
        try:
            return shlex.split(s)
        except ValueError as e:
            if str(e) == "No closing quotation":
                # e.g.   eggs "bacon ham
                # -> we fix this as   eggs "bacon ham"
                s += '"'
            elif str(e) == "No escaped character":
                # e.g.   eggs\
                # -> we fix this as  eggs\\
                s += '\\'
            else:
                raise


def shell_escape(s):
    """Escape a string so it's safe to pass to a shell."""
    if sys.platform.startswith('win'):
        # Oh dear flying sphagetti monster please kill me now...
        if not s:
            # Is this an empty argument or a literal ""? It seems to depend on
            # something magical.
            return '""'
        # We could also use \", but what do we do for a literal \" then? It
        # seems \\\". But \\ anywhere else is a literal \\. Because that makes
        # sense. Totally NOT. Using """ also seems to yield " and work in some
        # kind-of-safe manner.
        s = s.replace('"', '"""')
        # Some places suggest we use %% to escape %, but actually ^% seems to
        # work better (compare  echo %%DATE%%  and  echo ^%DATE^%)
        s = re.sub(r'[&|^><%]', r'^\g<0>', s)
        # Is everything escaped now? Maybe. I don't know. I don't *get* the
        # black magic Microshit is doing here.
        return s
    else:
        return shlex.quote(s)


def pastebin(text):
    """Paste the text into a pastebin and return the URL."""
    api_url = 'http://paste.the-compiler.org/api/'
    data = {
        'text': text,
        'title': "qutebrowser crash",
        'name': "qutebrowser",
    }
    encoded_data = urlencode(data).encode('utf-8')
    create_url = urljoin(api_url, 'create')
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'
    }
    request = urllib.request.Request(create_url, encoded_data, headers)
    response = urllib.request.urlopen(request)
    url = response.read().decode('utf-8').rstrip()
    if not url.startswith('http'):
        raise ValueError("Got unexpected response: {}".format(url))
    return url


def get_standard_dir(typ):
    """Get the directory where files of the given type should be written to.

    Args:
        typ: A member of the QStandardPaths::StandardLocation enum,
             see http://qt-project.org/doc/qt-5/qstandardpaths.html#StandardLocation-enum
    """
    qapp = QCoreApplication.instance()
    orgname = qapp.organizationName()
    # We need to temporarely unset the organisationname here since the
    # webinspector wants it to be set to store its persistent data correctly,
    # but we don't want that to happen.
    qapp.setOrganizationName(None)
    try:
        path = QStandardPaths.writableLocation(typ)
        if not path:
            raise ValueError("QStandardPaths returned an empty value!")
        # Qt seems to use '/' as path separator even on Windows...
        path = path.replace('/', os.sep)
        appname = qapp.applicationName()
        if (typ == QStandardPaths.ConfigLocation and
                path.split(os.sep)[-1] != appname):
            # Workaround for
            # https://bugreports.qt-project.org/browse/QTBUG-38872
            path = os.path.join(path, appname)
        if not os.path.exists(path):
            os.makedirs(path)
        return path
    finally:
        qapp.setOrganizationName(orgname)


def actute_warning():
    """Display a warning about the dead_actute issue if needed."""
    # Non linux OS' aren't affected
    if not sys.platform.startswith('linux'):
        return
    # If no compose file exists for some reason, we're not affected
    if not os.path.exists('/usr/share/X11/locale/en_US.UTF-8/Compose'):
        return
    # Qt >= 5.3 doesn't seem to be affected
    try:
        if qt_version_check('5.3.0'):
            return
    except ValueError:
        pass
    with open('/usr/share/X11/locale/en_US.UTF-8/Compose', 'r') as f:
        for line in f:
            if '<dead_actute>' in line:
                if sys.stdout is not None:
                    sys.stdout.flush()
                print("Note: If you got a 'dead_actute' warning above, that "
                      "is not a bug in qutebrowser! See "
                      "https://bugs.freedesktop.org/show_bug.cgi?id=69476 for "
                      "details.")
                break


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

    Raise:
        ValueError if the percentage was invalid.
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
        colorspace: The desired interpolation colorsystem,
                    QColor::{Rgb,Hsv,Hsl} (from QColor::Spec enum)

    Return:
        The interpolated QColor, with the same spec as the given start color.

    Raise:
        ValueError if invalid parameters are passed.
    """
    if not start.isValid():
        raise ValueError("Invalid start color")
    if not end.isValid():
        raise ValueError("Invalid end color")
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
    return out.convertTo(start.spec())


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


def check_print_compat():
    """Check if printing should work in the given Qt version."""
    return not (os.name == 'nt' and qt_version_check('5.3.0', operator.lt))


def get_http_header(reply, headername, param=None):
    """Get a parameter from a HTTP header.

    Note we use the email value to get a HTTP header, because they're both MIME
    headers and email supports that.

    Args:
        reply: The QNetworkReply to get the header from.
        headername: The name of the header.
        param: The name of the param to get, or None to get the whole contents.

    Return:
        The data as a string, or None if the data wasn't found.

    FIXME add tests
    """
    if not reply.hasRawHeader(headername):
        return None
    header = (headername.encode('ascii') + b': ' +
              bytes(reply.rawHeader(headername)))
    msg = email.message_from_bytes(header, policy=email.policy.HTTP)
    if param is not None:
        return msg.get_param(param, header=headername)
    else:
        return msg.get(headername, None)


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
