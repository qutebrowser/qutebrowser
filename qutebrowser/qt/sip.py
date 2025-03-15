# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=wildcard-import,unused-wildcard-import

"""Wrapped Qt imports for PyQt5.sip/PyQt6.sip.

All code in qutebrowser should use this module instead of importing from
PyQt/sip directly. This allows supporting both Qt 5 and Qt 6.

See machinery.py for details on how Qt wrapper selection works.

Any API exported from this module is based on the PyQt6.sip API:
https://www.riverbankcomputing.com/static/Docs/PyQt6/api/sip/sip-module.html

Note that we don't yet abstract between PySide/PyQt here.
"""

from qutebrowser.qt import machinery

machinery.init_implicit()

if machinery.USE_PYSIDE6:  # pylint: disable=no-else-raise
    raise machinery.Unavailable()
elif machinery.USE_PYQT5:
    try:
        from PyQt5.sip import *
    except ImportError:
        from sip import *  # type: ignore[import-not-found]
elif machinery.USE_PYQT6:
    try:
        from PyQt6.sip import *
    except ImportError:
        # While upstream recommends using PyQt5.sip ever since PyQt5 5.11, some
        # distributions still package later versions of PyQt5 with a top-level
        # "sip" rather than "PyQt5.sip".
        from sip import *  # type: ignore[import-not-found]
else:
    raise machinery.UnknownWrapper()
