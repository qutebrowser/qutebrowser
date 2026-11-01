# SPDX-FileCopyrightText: Freya Bruhin (The-Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
        from Tkinter import Tk  # type: ignore[import-not-found, no-redef]
        import tkMessageBox as messagebox  # type: ignore[import-not-found, no-redef] # noqa: N813
    except ImportError:
        # Some Python without Tk
        Tk = None  # type: ignore[misc, assignment]
        messagebox = None  # type: ignore[assignment]


MIN_PYTHON_VERSION = (3, 10)
MIN_PYTHON_VERSION_STR = '.'.join(map(str, MIN_PYTHON_VERSION))


# First we check the version of Python. This code should run fine with python2
# and python3. We don't have Qt available here yet, so we just print an error
# to stderr.
def check_python_version():
    """Check if correct python version is run."""
    if sys.version_info[:2] < MIN_PYTHON_VERSION:
        # We don't use .format() and print_function here just in case someone
        # still has < 2.6 installed.
        version_str = '.'.join(map(str, sys.version_info[:3]))
        text = ("At least Python " + MIN_PYTHON_VERSION_STR + " is required to run "
                "qutebrowser, but it's running with " + version_str + ".\n")

        show_errors = '--no-err-windows' not in sys.argv
        if Tk and show_errors:  # type: ignore[truthy-function]  # pragma: no cover
            root = Tk()
            root.withdraw()
            messagebox.showerror("qutebrowser: Fatal error!", text)
        else:
            sys.stderr.write(text)
            sys.stderr.flush()
        sys.exit(1)


if __name__ == '__main__':
    check_python_version()
