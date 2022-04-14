from qutebrowser.qt import machinery


if machinery.USE_PYQT5:
    from PyQt5.QtQml import *
elif machinery.USE_PYQT6:
    from PyQt6.QtQml import *
elif machinery.USE_PYSIDE2:
    from PySide2.QtQml import *
elif machinery.USE_PYSIDE6:
    from PySide6.QtQml import *
