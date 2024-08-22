# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=import-error,wildcard-import,unused-wildcard-import,unused-import

"""Wrapped Qt imports for Qt WebEngine Core.

All code in qutebrowser should use this module instead of importing from
PyQt/PySide directly. This allows supporting both Qt 5 and Qt 6.

See machinery.py for details on how Qt wrapper selection works.

Any API exported from this module is based on the Qt 6 API:
https://doc.qt.io/qt-6/qtwebenginecore-index.html
"""

from qutebrowser.qt import machinery

machinery.init_implicit()


if machinery.USE_PYSIDE6:
    from PySide6.QtWebEngineCore import *
elif machinery.USE_PYQT5:
    from PyQt5.QtWebEngineCore import *
    from PyQt5.QtWebEngineWidgets import (
        QWebEngineSettings,
        QWebEngineProfile,
        QWebEngineDownloadItem as QWebEngineDownloadRequest,
        QWebEnginePage,
        QWebEngineCertificateError,
        QWebEngineScript,
        QWebEngineHistory,
        QWebEngineHistoryItem,
        QWebEngineScriptCollection,
        QWebEngineClientCertificateSelection,
        QWebEngineFullScreenRequest,
        QWebEngineContextMenuData as QWebEngineContextMenuRequest,
    )
    from PyQt5.QtWebEngine import PYQT_WEBENGINE_VERSION, PYQT_WEBENGINE_VERSION_STR
elif machinery.USE_PYQT6:
    from PyQt6.QtWebEngineCore import *
else:
    raise machinery.UnknownWrapper()
