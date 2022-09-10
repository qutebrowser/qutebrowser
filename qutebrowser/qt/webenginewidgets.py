# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# FIXME:qt6 (lint)
# pylint: disable=missing-module-docstring,import-error,wildcard-import,unused-wildcard-import
# flake8: noqa

from qutebrowser.qt import machinery


if machinery.USE_PYQT5:
    from PyQt5.QtWebEngineWidgets import *
elif machinery.USE_PYQT6:
    from PyQt6.QtWebEngineWidgets import *
elif machinery.USE_PYSIDE6:
    from PySide6.QtWebEngineWidgets import *
else:
    raise machinery.UnknownWrapper()


if machinery.IS_QT5:
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
