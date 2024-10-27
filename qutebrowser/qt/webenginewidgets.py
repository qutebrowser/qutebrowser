# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=import-error,wildcard-import,unused-wildcard-import

"""Wrapped Qt imports for Qt WebEngine Widgets.

All code in qutebrowser should use this module instead of importing from
PyQt/PySide directly. This allows supporting both Qt 5 and Qt 6.

See machinery.py for details on how Qt wrapper selection works.

Any API exported from this module is based on the Qt 6 API:
https://doc.qt.io/qt-6/qtwebenginewidgets-index.html
"""

from qutebrowser.qt import machinery

machinery.init_implicit()


if machinery.USE_PYSIDE6:
    from PySide6.QtWebEngineWidgets import *
elif machinery.USE_PYQT5:
    from PyQt5.QtWebEngineWidgets import *
elif machinery.USE_PYQT6:
    from PyQt6.QtWebEngineWidgets import *
else:
    raise machinery.UnknownWrapper()


if machinery.IS_QT5:
    # pylint: disable=undefined-variable
    # moved to WebEngineCore in Qt 6
    del QWebEngineSettings
    del QWebEngineProfile
    del QWebEngineDownloadItem
    del QWebEnginePage
    del QWebEngineCertificateError
    del QWebEngineScript
    del QWebEngineHistory
    del QWebEngineHistoryItem
    del QWebEngineScriptCollection
    del QWebEngineClientCertificateSelection
    del QWebEngineFullScreenRequest
    del QWebEngineContextMenuData
