use_pyqt5 = False
use_pyqt6 = True
use_pyside2 = False
use_pyside6 = False


class Error(Exception):
    pass


class Unavailable(Error, ImportError):
    pass


class UnknownWrapper(Error):
    pass
