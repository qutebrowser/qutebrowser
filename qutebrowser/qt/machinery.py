# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# pyright: reportConstantRedefinition=false

"""Qt wrapper selection.

Contains selection logic and globals for Qt wrapper selection.
"""

import os
import sys
import enum
import argparse
import importlib
import dataclasses
from typing import Optional

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
        super().__init__(f"Unavailable with {INFO.wrapper}")


class UnknownWrapper(Error):
    """Raised when an Qt module is imported but the wrapper values are unknown.

    Should never happen (unless a new wrapper is added).
    """


class SelectionReason(enum.Enum):

    """Reasons for selecting a Qt wrapper."""

    #: The wrapper was selected via --qt-wrapper.
    CLI = "--qt-wrapper"

    #: The wrapper was selected via the QUTE_QT_WRAPPER environment variable.
    ENV = "QUTE_QT_WRAPPER"

    #: The wrapper was selected via autoselection.
    AUTO = "autoselect"

    #: The default wrapper was selected.
    DEFAULT = "default"

    #: The wrapper was faked/patched out (e.g. in tests).
    FAKE = "fake"

    #: The reason was not set.
    UNKNOWN = "unknown"


@dataclasses.dataclass
class SelectionInfo:
    """Information about outcomes of importing Qt wrappers."""

    pyqt5: Optional[str] = None
    pyqt6: Optional[str] = None
    wrapper: Optional[str] = None
    reason: SelectionReason = SelectionReason.UNKNOWN

    def set_module(self, name: str, outcome: str) -> None:
        """Set the outcome for a module import."""
        setattr(self, name.lower(), outcome)

    def __str__(self) -> str:
        lines = ["Qt wrapper:"]
        if self.pyqt5 is not None:
            lines.append(f"PyQt5: {self.pyqt5}")
        if self.pyqt6 is not None:
            lines.append(f"PyQt6: {self.pyqt6}")

        lines.append(f"selected: {self.wrapper} (via {self.reason.value})")
        return "\n".join(lines)


def _autoselect_wrapper() -> SelectionInfo:
    """Autoselect a Qt wrapper.

    This goes through all wrappers defined in WRAPPER.
    The first one which can be imported is returned.
    """
    info = SelectionInfo(reason=SelectionReason.AUTO)

    for wrapper in WRAPPERS:
        try:
            importlib.import_module(wrapper)
        except ImportError as e:
            info.set_module(wrapper, str(e))
            continue

        info.set_module(wrapper, "success")
        info.wrapper = wrapper
        return info

    # FIXME return a SelectionInfo here instead so we can handle this in earlyinit?
    wrappers = ", ".join(WRAPPERS)
    raise Error(f"No Qt wrapper found, tried {wrappers}")


def _select_wrapper(args: Optional[argparse.Namespace]) -> SelectionInfo:
    """Select a Qt wrapper.

    - If --qt-wrapper is given, use that.
    - Otherwise, if the QUTE_QT_WRAPPER environment variable is set, use that.
    - Otherwise, use PyQt5 (FIXME:qt6 autoselect).
    """
    if args is not None and args.qt_wrapper is not None:
        assert args.qt_wrapper in WRAPPERS, args.qt_wrapper  # ensured by argparse
        return SelectionInfo(wrapper=args.qt_wrapper, reason=SelectionReason.CLI)

    env_var = "QUTE_QT_WRAPPER"
    env_wrapper = os.environ.get(env_var)
    if env_wrapper is not None:
        if env_wrapper not in WRAPPERS:
            raise Error(f"Unknown wrapper {env_wrapper} set via {env_var}, "
                        f"allowed: {', '.join(WRAPPERS)}")
        return SelectionInfo(wrapper=env_wrapper, reason=SelectionReason.ENV)

    # FIXME:qt6 Go back to the auto-detection once ready
    # FIXME:qt6 Make sure to still consider _DEFAULT_WRAPPER for packagers
    # (rename to _WRAPPER_OVERRIDE since our sed command is broken anyways then?)
    # return _autoselect_wrapper()
    return SelectionInfo(wrapper=_DEFAULT_WRAPPER, reason=SelectionReason.DEFAULT)


# Values are set in init(). If you see a NameError here, it means something tried to
# import Qt (or check for its availability) before machinery.init() was called.

#: Information about the wrapper that ended up being selected.
#: Should not be used directly, use one of the USE_* or IS_* constants below
#: instead, as those are supported by type checking.
INFO: SelectionInfo

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

_initialized = False


def init(args: Optional[argparse.Namespace] = None) -> None:
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
    global INFO, USE_PYQT5, USE_PYQT6, USE_PYSIDE6, IS_QT5, IS_QT6, \
        IS_PYQT, IS_PYSIDE, _initialized

    if args is None:
        # Implicit initialization can happen multiple times
        # (all subsequent calls are a no-op)
        if _initialized:
            return
    else:
        # Explicit initialization can happen exactly once, and if it's used, there
        # should not be any implicit initialization (qutebrowser.qt imports) before it.
        if _initialized:  # pylint: disable=else-if-used
            raise Error("init() already called before application init")
    _initialized = True

    for name in WRAPPERS:
        # If any Qt wrapper has been imported before this, all hope is lost.
        if name in sys.modules:
            raise Error(f"{name} already imported")

    INFO = _select_wrapper(args)
    USE_PYQT5 = INFO.wrapper == "PyQt5"
    USE_PYQT6 = INFO.wrapper == "PyQt6"
    USE_PYSIDE6 = INFO.wrapper == "PySide6"
    assert USE_PYQT5 ^ USE_PYQT6 ^ USE_PYSIDE6

    IS_QT5 = USE_PYQT5
    IS_QT6 = USE_PYQT6 or USE_PYSIDE6
    IS_PYQT = USE_PYQT5 or USE_PYQT6
    IS_PYSIDE = USE_PYSIDE6
    assert IS_QT5 ^ IS_QT6
    assert IS_PYQT ^ IS_PYSIDE
