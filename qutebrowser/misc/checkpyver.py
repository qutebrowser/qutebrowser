# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
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

"""Check if qutebrowser is run with the correct python version.

This should import and run fine with both python2 and python3.
"""

import sys

try:
    # Python3
    from tkinter import Tk, messagebox
except ImportError:  # pragma: no cover
    try:
        # Python2
        from Tkinter import Tk
        import tkMessageBox as messagebox
    except ImportError:
        # Some Python without Tk
        Tk = None
        messagebox = None


# First we check the version of Python. This code should run fine with python2
# and python3. We don't have Qt available here yet, so we just print an error
# to stderr.
def check_python_version():
    """Check if correct python version is run."""
    if sys.hexversion < 0x03040000:
        # We don't use .format() and print_function here just in case someone
        # still has < 2.6 installed.
        # pylint: disable=bad-builtin
        version_str = '.'.join(map(str, sys.version_info[:3]))
        text = ("At least Python 3.4 is required to run qutebrowser, but " +
                version_str + " is installed!\n")
        if Tk and '--no-err-windows' not in sys.argv:  # pragma: no cover
            root = Tk()
            root.withdraw()
            messagebox.showerror("qutebrowser: Fatal error!", text)
        else:
            sys.stderr.write(text)
            sys.stderr.flush()
        sys.exit(1)


if __name__ == '__main__':
    check_python_version()
