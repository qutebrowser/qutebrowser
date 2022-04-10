from qutebrowser.qt import machinery


if machinery.use_pyqt5:
    from PyQt5.QtWebKitWidgets import *
elif machinery.use_pyqt6:
    raise machinery.Unavailable()
elif machinery.use_pyside2:
    raise machinery.Unavailable()
elif machinery.use_pyside6:
    raise machinery.Unavailable()
else:
    raise machinery.UnknownWrapper()
