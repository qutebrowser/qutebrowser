from qutebrowser.qt import machinery


if machinery.USE_PYQT5:
    from PyQt5.QtWidgets import *
elif machinery.USE_PYQT6:
    from PyQt6.QtWidgets import *
elif machinery.USE_PYSIDE2:
    from PySide2.QtWidgets import *
elif machinery.USE_PYSIDE6:
    from PySide6.QtWidgets import *

if machinery.IS_QT5:
    del QFileSystemModel  # moved to QtGui in Qt 6
