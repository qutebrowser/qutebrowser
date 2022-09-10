# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# FIXME:qt6 (lint)
# pylint: disable=missing-module-docstring,import-error,wildcard-import,unused-wildcard-import,unused-import
# flake8: noqa

from qutebrowser.qt import machinery


if machinery.USE_PYQT5:
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
elif machinery.USE_PYSIDE6:
    from PySide6.QtWebEngineCore import *
else:
    raise machinery.UnknownWrapper()
