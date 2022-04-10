from qutebrowser.qt import machinery


if machinery.use_pyqt5:
    from PyQt5.QtWebEngineWidgets import *
    # moved to WebEngineCore in Qt 6
    del QWebEngineSettings
    del QWebEngineProfile
    del QWebEngineDownloadItem
elif machinery.use_pyqt6:
    from PyQt6.QtWebEngineWidgets import *
elif machinery.use_pyside2:
    from PySide2.QtWebEngineWidgets import *
    # moved to WebEngineCore in Qt 6
    del QWebEngineSettings
    del QWebEngineProfile
    del QWebEngineDownloadItem
elif machinery.use_pyside6:
    from PySide6.QtWebEngineWidgets import *
else:
    raise machinery.UnknownWrapper()
