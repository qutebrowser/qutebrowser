# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# pyright: reportConstantRedefinition=false

"""Qt wrapper selection.

Contains selection logic and globals for Qt wrapper selection.
"""

import os
import sys
import argparse
import importlib
from typing import Union

# Packagers: Patch the line below to change the default wrapper for Qt 6 packages, e.g.:
# sed -i 's/_DEFAULT_WRAPPER = "PyQt5"/_DEFAULT_WRAPPER = "PyQt6"/' qutebrowser/qt/machinery.py
#
# Users: Set the QUTE_QT_WRAPPER environment variable to change the default wrapper.
_DEFAULT_WRAPPER = "PyQt5"

WRAPPERS = [
    "PyQt6",
    "PyQt5",
    # Needs more work
    # "PySide6",
]


class Error(Exception):
    """Base class for all exceptions in this module."""


class Unavailable(Error, ImportError):

    """Raised when a module is unavailable with the given wrapper."""

    def __init__(self) -> None:
        super().__init__(f"Unavailable with {WRAPPER}")


class UnknownWrapper(Error):
    """Raised when an Qt module is imported but the wrapper values are unknown.

    Should never happen (unless a new wrapper is added).
    """


def _autoselect_wrapper() -> str:
    """Autoselect a Qt wrapper.

    This goes through all wrappers defined in WRAPPER.
    The first one which can be imported is returned.
    """
    for wrapper in WRAPPERS:
        try:
            importlib.import_module(wrapper)
        except ImportError:
            # FIXME:qt6 show/log this somewhere?
            continue
        return wrapper

    wrappers = ", ".join(WRAPPERS)
    raise Error(f"No Qt wrapper found, tried {wrappers}")


def _select_wrapper(args: Union[argparse.Namespace, None]) -> str:
    """Select a Qt wrapper.

    - If --qt-wrapper is given, use that.
    - Otherwise, if the QUTE_QT_WRAPPER environment variable is set, use that.
    - Otherwise, use PyQt5 (FIXME:qt6 autoselect).
    """
    if args is not None and args.qt_wrapper is not None:
        assert args.qt_wrapper in WRAPPERS, args.qt_wrapper  # ensured by argparse
        return args.qt_wrapper

    env_var = "QUTE_QT_WRAPPER"
    env_wrapper = os.environ.get(env_var)
    if env_wrapper is not None:
        if env_wrapper not in WRAPPERS:
            raise Error(f"Unknown wrapper {env_wrapper} set via {env_var}, "
                        f"allowed: {', '.join(WRAPPERS)}")
        return env_wrapper

    # FIXME:qt6 Go back to the auto-detection once ready
    # return _autoselect_wrapper()
    return _DEFAULT_WRAPPER


# Values are set in init(). If you see a NameError here, it means something tried to
# import Qt (or check for its availability) before machinery.init() was called.

#: The name of the wrapper to be used, one of WRAPPERS.
#: Should not be used directly, use one of the USE_* or IS_* constants below
#: instead, as those are supported by type checking.
WRAPPER: str

#: Whether we're using PyQt5. Consider using IS_QT5 or IS_PYQT instead.
USE_PYQT5: bool

#: Whether we're using PyQt6. Consider using IS_QT6 or IS_PYQT instead.
USE_PYQT6: bool

#: Whether we're using PySide6. Consider using IS_QT6 or IS_PYSIDE instead.
USE_PYSIDE6: bool

#: Whether we are using any Qt 5 wrapper.
IS_QT5: bool

#: Whether we are using any Qt 6 wrapper.
IS_QT6: bool

#: Whether we are using any PyQt wrapper.
IS_PYQT: bool

#: Whether we are using any PySide wrapper.
IS_PYSIDE: bool

#: The name of the package imported.
PACKAGE: str

_initialized = False


def init(args: Union[argparse.Namespace, None] = None) -> None:
    """Initialize Qt wrapper globals.

    There is two ways how this function can be called:

    - Explicitly, during qutebrowser startup, where it gets called before
      earlyinit.early_init() in qutebrowser.py (i.e. after we have an argument
      parser, but before any kinds of Qt usage). This allows `args` to be passed,
      which is used to select the Qt wrapper (if --qt-wrapper is given).

    - Implicitly, when any of the qutebrowser.qt.* modules in this package is imported.
      This should never happen during normal qutebrowser usage, but means that any
      qutebrowser module can be imported without having to worry about machinery.init().
      This is useful for e.g. tests or manual interactive usage of the qutebrowser code.
      In this case, `args` will be None.
    """
    global WRAPPER, USE_PYQT5, USE_PYQT6, USE_PYSIDE6, IS_QT5, IS_QT6, \
        IS_PYQT, IS_PYSIDE, PACKAGE, _initialized

    if args is None:
        # Implicit initialization can happen multiple times
        # (all subsequent calls are a no-op)
        if _initialized:
            return
    else:
        # Explicit initialization can happen exactly once, and if it's used, there
        # should not be any implicit initialization (qutebrowser.qt imports) before it.
        assert not _initialized, "init() already called before application init"
    _initialized = True

    for name in WRAPPERS:
        # If any Qt wrapper has been imported before this, all hope is lost.
        assert name not in sys.modules, f"{name} already imported"

    WRAPPER = _select_wrapper(args)
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
