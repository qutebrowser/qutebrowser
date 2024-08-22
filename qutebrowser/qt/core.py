# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=import-error,wildcard-import,unused-wildcard-import

"""Wrapped Qt imports for Qt Core.

All code in qutebrowser should use this module instead of importing from
PyQt/PySide directly. This allows supporting both Qt 5 and Qt 6.

See machinery.py for details on how Qt wrapper selection works.

Any API exported from this module is based on the Qt 6 API:
https://doc.qt.io/qt-6/qtcore-index.html
"""

from typing import TYPE_CHECKING
from qutebrowser.qt import machinery

machinery.init_implicit()


if machinery.USE_PYSIDE6:
    from PySide6.QtCore import *
elif machinery.USE_PYQT5:
    from PyQt5.QtCore import *
elif machinery.USE_PYQT6:
    from PyQt6.QtCore import *

    if TYPE_CHECKING:
        from qutebrowser.qt._core_pyqtproperty import pyqtProperty
else:
    raise machinery.UnknownWrapper()
