# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# FIXME:qt6 (lint)
# pylint: disable=missing-module-docstring
# flake8: noqa

import os
import importlib

# Packagers: Patch the line below to change the default wrapper for Qt 6 packages, e.g.:
# sed -i 's/_DEFAULT_WRAPPER = "PyQt5"/_DEFAULT_WRAPPER = "PyQt6"/' qutebrowser/qt/machinery.py
#
# Users: Set the QUTE_QT_WRAPPER environment variable to change the default wrapper.
_DEFAULT_WRAPPER = "PyQt5"

_WRAPPERS = [
    "PyQt6",
    "PyQt5",
    # Needs more work
    # "PySide6",
]


class Error(Exception):
    pass


class Unavailable(Error, ImportError):

    """Raised when a module is unavailable with the given wrapper."""

    def __init__(self) -> None:
        super().__init__(f"Unavailable with {WRAPPER}")


class UnknownWrapper(Error):
    pass


def _autoselect_wrapper():
    for wrapper in _WRAPPERS:
        try:
            importlib.import_module(wrapper)
        except ImportError:
            # FIXME:qt6 show/log this somewhere?
            continue
        return wrapper

    wrappers = ", ".join(_WRAPPERS)
    raise Error(f"No Qt wrapper found, tried {wrappers}")


def _select_wrapper():
    env_var = "QUTE_QT_WRAPPER"
    env_wrapper = os.environ.get(env_var)
    if env_wrapper is None:
        # FIXME:qt6 Go back to the auto-detection once ready
        # return _autoselect_wrapper()
        return _DEFAULT_WRAPPER

    if env_wrapper not in _WRAPPERS:
        raise Error(f"Unknown wrapper {env_wrapper} set via {env_var}, "
                    f"allowed: {', '.join(_WRAPPERS)}")

    return env_wrapper


WRAPPER = _select_wrapper()
USE_PYQT5 = WRAPPER == "PyQt5"
USE_PYQT6 = WRAPPER == "PyQt6"
USE_PYSIDE6 = WRAPPER == "PySide6"
assert USE_PYQT5 ^ USE_PYQT6 ^ USE_PYSIDE6

IS_QT5 = USE_PYQT5
IS_QT6 = USE_PYQT6 or USE_PYSIDE6
IS_PYQT = USE_PYQT5 or USE_PYQT6
IS_PYSIDE = USE_PYSIDE6
assert IS_QT5 ^ IS_QT6
assert IS_PYQT ^ IS_PYSIDE


if USE_PYQT5:
    PACKAGE = "PyQt5"
elif USE_PYQT6:
    PACKAGE = "PyQt6"
elif USE_PYSIDE6:
    PACKAGE = "PySide6"
