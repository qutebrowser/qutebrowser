# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Wrappers around Qt/PyQt code."""

# pylint: disable=unused-import,import-error
import importlib

PyQt5 = PyQt6 = False
try:
    import PyQt5 as pyqt  # noqa: N813
    PyQt5 = True
except ImportError:
    import PyQt6 as pyqt  # type: ignore[import, no-redef] # noqa: N813
    PyQt6 = True

# While upstream recommends using PyQt5.sip ever since PyQt5 5.11, some distributions
# still package later versions of PyQt5 with a top-level "sip" rather than "PyQt5.sip".
try:
    if PyQt5:
        from PyQt5 import sip
    elif PyQt6:
        from PyQt6 import sip  # type: ignore[no-redef]
except ImportError:
    import sip  # type: ignore[import, no-redef]

# pylint: disable=ungrouped-imports
if PyQt5:
    from PyQt5 import QtCore
    from PyQt5 import QtDBus
    from PyQt5 import QtGui
    from PyQt5 import QtNetwork
    from PyQt5 import QtPrintSupport
    from PyQt5 import QtQml
    from PyQt5 import QtSql
    from PyQt5 import QtWidgets
    from PyQt5 import QtTest
elif PyQt6:
    from PyQt6 import QtCore  # type: ignore[no-redef]
    from PyQt6 import QtDBus  # type: ignore[no-redef]
    from PyQt6 import QtGui  # type: ignore[no-redef]
    from PyQt6 import QtNetwork  # type: ignore[no-redef]
    from PyQt6 import QtPrintSupport  # type: ignore[no-redef]
    from PyQt6 import QtQml  # type: ignore[no-redef]
    from PyQt6 import QtSql  # type: ignore[no-redef]
    from PyQt6 import QtWidgets  # type: ignore[no-redef]
    from PyQt6 import QtTest  # type: ignore[no-redef]

try:
    if PyQt5:
        from PyQt5 import QtWebEngine
        from PyQt5 import QtWebEngineCore
        from PyQt5 import QtWebEngineWidgets
    elif PyQt6:
        from PyQt6 import QtWebEngine  # type: ignore[no-redef]
        from PyQt6 import QtWebEngineCore  # type: ignore[no-redef]
        from PyQt6 import QtWebEngineWidgets  # type: ignore[no-redef]
except ImportError:
    QtWebEngine = None  # type: ignore[assignment]
    QtWebEngineCore = None  # type: ignore[assignment]
    QtWebEngineWidgets = None  # type: ignore[assignment]

try:
    if PyQt5:
        from PyQt5 import QtWebKit
        from PyQt5 import QtWebKitWidgets
    elif PyQt6:
        from PyQt6 import QtWebKit  # type: ignore[no-redef]
        from PyQt6 import QtWebKitWidgets  # type: ignore[no-redef]
except ImportError:
    QtWebKit = None  # type: ignore[assignment]
    QtWebKitWidgets = None  # type: ignore[assignment]
