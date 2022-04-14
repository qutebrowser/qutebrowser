from qutebrowser.qt import machinery


if machinery.USE_PYQT5:
    from PyQt5.QtDBus import *
elif machinery.USE_PYQT6:
    from PyQt6.QtDBus import *
elif machinery.USE_PYSIDE2:
    from PySide2.QtDBus import *
elif machinery.USE_PYSIDE6:
    from PySide6.QtDBus import *
