from qutebrowser.qt import machinery


if machinery.use_pyqt5:
    from PyQt5.QtDBus import *
elif machinery.use_pyqt6:
    from PyQt6.QtDBus import *
elif machinery.use_pyside2:
    from PySide2.QtDBus import *
elif machinery.use_pyside6:
    from PySide6.QtDBus import *
