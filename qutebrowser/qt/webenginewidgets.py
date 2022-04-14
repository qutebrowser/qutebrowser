from qutebrowser.qt import machinery


if machinery.USE_PYQT5:
    from PyQt5.QtWebEngineWidgets import *
elif machinery.USE_PYQT6:
    from PyQt6.QtWebEngineWidgets import *
elif machinery.USE_PYSIDE2:
    from PySide2.QtWebEngineWidgets import *
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
