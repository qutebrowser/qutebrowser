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

try:
    import PyQt5 as pyqt  # noqa: N813
except ImportError:
    import PyQt6 as pyqt  # type: ignore[import, no-redef] # noqa: N813

# While upstream recommends using PyQt5.sip ever since PyQt5 5.11, some distributions
# still package later versions of PyQt5 with a top-level "sip" rather than "PyQt5.sip".
# pylint: disable=ungrouped-imports
try:
    sip = importlib.import_module(f"{pyqt.__name__}.sip")
except ImportError:
    import sip  # type: ignore[import, no-redef]

QtCore = importlib.import_module(f"{pyqt.__name__}.QtCore")
QtDBus = importlib.import_module(f"{pyqt.__name__}.QtDBus")
QtGui = importlib.import_module(f"{pyqt.__name__}.QtGui")
QtNetwork = importlib.import_module(f"{pyqt.__name__}.QtNetwork")
QtPrintSupport = importlib.import_module(f"{pyqt.__name__}.QtPrintSupport")
QtQml = importlib.import_module(f"{pyqt.__name__}.QtQml")
QtSql = importlib.import_module(f"{pyqt.__name__}.QtSql")
QtWidgets = importlib.import_module(f"{pyqt.__name__}.QtWidgets")

try:
    QtWebEngine = importlib.import_module(f"{pyqt.__name__}.QtWebEngine")
    QtWebEngineCore = importlib.import_module(f"{pyqt.__name__}.QtWebEngineCore")
    QtWebEngineWidgets = importlib.import_module(f"{pyqt.__name__}.QtWebEngineWidgets")
except ImportError:
    QtWebEngine = None
    QtWebEngineCore = None
    QtWebEngineWidgets = None

try:
    QtWebKit = importlib.import_module(f"{pyqt.__name__}.QtWebKit")
    QtWebKitWidgets = importlib.import_module(f"{pyqt.__name__}.QtWebKitWidgets")
except ImportError:
    QtWebKit = None
    QtWebKitWidgets = None
