from qutebrowser.qt import machinery


if machinery.use_pyqt5:
    from PyQt5.QtWebEngineCore import *
    from PyQt5.QtWebEngineWidgets import (
        QWebEngineSettings,
        QWebEngineProfile,
        QWebEngineDownloadItem as QWebEngineDownloadRequest,
    )
    # FIXME:qt6 is there a PySide2 equivalent to those?
    from PyQt5.QtWebEngine import PYQT_WEBENGINE_VERSION, PYQT_WEBENGINE_VERSION_STR
elif machinery.use_pyqt6:
    from PyQt6.QtWebEngineCore import *
elif machinery.use_pyside2:
    from PySide2.QtWebEngineCore import *
    from PySide2.QtWebEngineWidgets import (
        QWebEngineSettings,
        QWebEngineProfile,
        QWebEngineDownloadItem as QWebEngineDownloadRequest,
    )
elif machinery.use_pyside6:
    from PySide6.QtWebEngineCore import *
else:
    raise machinery.UnknownWrapper()
