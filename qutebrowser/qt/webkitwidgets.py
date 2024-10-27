# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=wildcard-import,no-else-raise

"""Wrapped Qt imports for Qt WebKit Widgets.

All code in qutebrowser should use this module instead of importing from
PyQt/PySide directly. This allows supporting both Qt 5 and Qt 6
(though WebKit is only supported with Qt 5).

See machinery.py for details on how Qt wrapper selection works.

Any API exported from this module is based on the QtWebKit 5.212 API:
https://qtwebkit.github.io/doc/qtwebkit/qtwebkitwidgets-index.html
"""

import typing

from qutebrowser.qt import machinery

machinery.init_implicit()


if machinery.USE_PYSIDE6:
    raise machinery.Unavailable()
elif machinery.USE_PYQT5 or typing.TYPE_CHECKING:
    # If we use mypy (even on Qt 6), we pretend to have WebKit available.
    # This avoids central API (like BrowserTab) being Any because the webkit part of
    # the unions there is missing.
    # This causes various issues inside browser/webkit/, but we ignore those in
    # .mypy.ini because we don't really care much about QtWebKit anymore.
    from PyQt5.QtWebKitWidgets import *
elif machinery.USE_PYQT6:
    raise machinery.Unavailable()
else:
    raise machinery.UnknownWrapper()
