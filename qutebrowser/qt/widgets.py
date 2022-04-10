from qutebrowser.qt import machinery


if machinery.use_pyqt5:
    from PyQt5.QtWidgets import *
    del QFileSystemModel  # moved to QtGui in Qt 6
elif machinery.use_pyqt6:
    from PyQt6.QtWidgets import *
elif machinery.use_pyside2:
    from PySide2.QtWidgets import *
    del QFileSystemModel  # moved to QtGui in Qt 6
elif machinery.use_pyside6:
    from PySide6.QtWidgets import *
