use_pyqt5 = False
use_pyqt6 = True
use_pyside2 = False
use_pyside6 = False


if use_pyqt5:
    package = "PyQt5"
elif use_pyqt6:
    package = "PyQt6"
elif use_pyside2:
    package = "PySide2"
elif use_pyside6:
    package = "PySide6"


class Error(Exception):
    pass


class Unavailable(Error, ImportError):
    pass


class UnknownWrapper(Error):
    pass
