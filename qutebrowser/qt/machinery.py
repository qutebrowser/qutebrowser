import os
import importlib


_WRAPPERS = [
    "PyQt6",
    "PyQt5",
    # Need more work, PySide2 might not be usable at all
    # "PySide6",
    # "PySide2",
]


class Error(Exception):
    pass


class Unavailable(Error, ImportError):
    pass


class UnknownWrapper(Error):
    pass


def _autoselect_wrapper():
    for wrapper in _WRAPPERS:
        try:
            importlib.import_module(wrapper)
        except ImportError:
            # FIXME:qt6 show/log this somewhere?
            continue

        # FIXME:qt6 what to do if none are available?
        return wrapper


def _select_wrapper():
    env_var = "QUTE_QT_WRAPPER"
    env_wrapper = os.environ.get(env_var)
    if env_wrapper is None:
        return _autoselect_wrapper()

    if env_wrapper not in _WRAPPERS:
        raise Error(f"Unknown wrapper {env_wrapper} set via {env_var}, "
                    f"allowed: {', '.join(_WRAPPERS)}")

    return env_wrapper


WRAPPER = _select_wrapper()
USE_PYQT5 = WRAPPER == "PyQt5"
USE_PYQT6 = WRAPPER == "PyQt6"
USE_PYSIDE2 = WRAPPER == "PySide2"
USE_PYSIDE6 = WRAPPER == "PySide6"
assert USE_PYQT5 ^ USE_PYQT6 ^ USE_PYSIDE2 ^ USE_PYSIDE6

IS_QT5 = USE_PYQT5 or USE_PYSIDE2
IS_QT6 = USE_PYQT6 or USE_PYSIDE6
IS_PYQT = USE_PYQT5 or USE_PYQT6
IS_PYSIDE = USE_PYSIDE2 or USE_PYSIDE6
assert IS_QT5 ^ IS_QT6
assert IS_PYQT ^ IS_PYSIDE


if USE_PYQT5:
    PACKAGE = "PyQt5"
elif USE_PYQT6:
    PACKAGE = "PyQt6"
elif USE_PYSIDE2:
    PACKAGE = "PySide2"
elif USE_PYSIDE6:
    PACKAGE = "PySide6"
