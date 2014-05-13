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

"""Other utilities which don't fit anywhere else."""

import os
import re
import sys
import shlex
import os.path
import urllib.request
from urllib.parse import urljoin, urlencode
from functools import reduce

from PyQt5.QtCore import QCoreApplication, QStandardPaths

import qutebrowser


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
        from pkg_resources import resource_string
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
        # Backported from python's shlex because that's only available since
        # 3.3 and we might want to support 3.2.
        find_unsafe = re.compile(r'[^\w@%+=:,./-]', re.ASCII).search
        if not s:
            return "''"
        if find_unsafe(s) is None:
            return s
        # use single quotes, and put single quotes into double quotes
        # the string $'b is then quoted as '$'"'"'b'
        return "'" + s.replace("'", "'\"'\"'") + "'"


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
    path = QStandardPaths.writableLocation(typ)
    # Qt seems to use '/' as path separator even on Windows...
    path = path.replace('/', os.sep)
    appname = QCoreApplication.instance().applicationName()
    if (typ == QStandardPaths.ConfigLocation and
            path.split(os.sep)[-1] != appname):
        # Workaround for https://bugreports.qt-project.org/browse/QTBUG-38872
        path = os.path.join(path, appname)
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def actute_warning():
    """Display a warning about the dead_actute issue if needed."""
    if not (sys.platform.startswith('linux') and
            os.path.exists('/usr/share/X11/locale/en_US.UTF-8/Compose')):
        return
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
