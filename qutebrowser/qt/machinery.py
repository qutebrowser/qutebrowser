# pyright: reportConstantRedefinition=false

"""Qt wrapper selection.

Contains selection logic and globals for Qt wrapper selection.
"""

# NOTE: No qutebrowser or PyQt import should be done here (at import time),
# as some early initialization needs to take place before that!

import os
import sys
import enum
import html
import argparse
import warnings
import importlib
import dataclasses
from typing import Optional, Dict

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


class NoWrapperAvailableError(Error, ImportError):

    """Raised when no Qt wrapper is available."""

    def __init__(self, info: "SelectionInfo") -> None:
        super().__init__(f"No Qt wrapper was importable.\n\n{info}")


class UnknownWrapper(Error):
    """Raised when an Qt module is imported but the wrapper values are unknown.

    Should never happen (unless a new wrapper is added).
    """


class SelectionReason(enum.Enum):

    """Reasons for selecting a Qt wrapper."""

    #: The wrapper was selected via --qt-wrapper.
    cli = "--qt-wrapper"

    #: The wrapper was selected via the QUTE_QT_WRAPPER environment variable.
    env = "QUTE_QT_WRAPPER"

    #: The wrapper was selected via autoselection.
    auto = "autoselect"

    #: The default wrapper was selected.
    default = "default"

    #: The wrapper was faked/patched out (e.g. in tests).
    fake = "fake"

    #: The reason was not set.
    unknown = "unknown"


@dataclasses.dataclass
class SelectionInfo:
    """Information about outcomes of importing Qt wrappers."""

    wrapper: Optional[str] = None
    outcomes: Dict[str, str] = dataclasses.field(default_factory=dict)
    reason: SelectionReason = SelectionReason.unknown

    def set_module_error(self, name: str, error: Exception) -> None:
        """Set the outcome for a module import."""
        self.outcomes[name] = f"{type(error).__name__}: {error}"

    def use_wrapper(self, wrapper: str) -> None:
        """Set the wrapper to use."""
        self.wrapper = wrapper
        self.outcomes[wrapper] = "success"

    def __str__(self) -> str:
        if not self.outcomes:
            # No modules were tried to be imported (no autoselection)
            # Thus, we can have a shorter output instead of adding noise.
            return f"Qt wrapper: {self.wrapper} (via {self.reason.value})"

        lines = ["Qt wrapper info:"]
        for wrapper in WRAPPERS:
            outcome = self.outcomes.get(wrapper, "not imported")
            lines.append(f"  {wrapper}: {outcome}")

        lines.append(f"  -> selected: {self.wrapper} (via {self.reason.value})")
        return "\n".join(lines)

    def to_html(self) -> str:
        return html.escape(str(self)).replace("\n", "<br>")


def _autoselect_wrapper() -> SelectionInfo:
    """Autoselect a Qt wrapper.

    This goes through all wrappers defined in WRAPPER.
    The first one which can be imported is returned.
    """
    info = SelectionInfo(reason=SelectionReason.auto)

    for wrapper in WRAPPERS:
        try:
            importlib.import_module(wrapper)
        except ModuleNotFoundError as e:
            # Wrapper not available -> try the next one.
            info.set_module_error(wrapper, e)
            continue
        except ImportError as e:
            # Any other ImportError -> stop to surface the error.
            info.set_module_error(wrapper, e)
            break

        # Wrapper imported successfully -> use it.
        info.use_wrapper(wrapper)
        return info

    # SelectionInfo with wrapper=None but all error reports
    return info


def _select_wrapper(args: Optional[argparse.Namespace]) -> SelectionInfo:
    """Select a Qt wrapper.

    - If --qt-wrapper is given, use that.
    - Otherwise, if the QUTE_QT_WRAPPER environment variable is set, use that.
    - Otherwise, use PyQt5 (FIXME:qt6 autoselect).
    """
    # If any Qt wrapper has been imported before this, something strange might
    # be happening.
    for name in WRAPPERS:
        if name in sys.modules:
            warnings.warn(f"{name} already imported", stacklevel=1)

    if args is not None and args.qt_wrapper is not None:
        assert args.qt_wrapper in WRAPPERS, args.qt_wrapper  # ensured by argparse
        return SelectionInfo(wrapper=args.qt_wrapper, reason=SelectionReason.cli)

    env_var = "QUTE_QT_WRAPPER"
    env_wrapper = os.environ.get(env_var)
    if env_wrapper:
        if env_wrapper == "auto":
            return _autoselect_wrapper()
        elif env_wrapper not in WRAPPERS:
            raise Error(f"Unknown wrapper {env_wrapper} set via {env_var}, "
                        f"allowed: {', '.join(WRAPPERS)}")
        return SelectionInfo(wrapper=env_wrapper, reason=SelectionReason.env)

    # FIXME:qt6 Go back to the auto-detection once ready
    # FIXME:qt6 Make sure to still consider _DEFAULT_WRAPPER for packagers
    # (rename to _WRAPPER_OVERRIDE since our sed command is broken anyways then?)
    # return _autoselect_wrapper()
    return SelectionInfo(wrapper=_DEFAULT_WRAPPER, reason=SelectionReason.default)


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


def _set_globals(info: SelectionInfo) -> None:
    """Set all global variables in this module based on the given SelectionInfo.

    Those are split into multiple global variables because that way we can teach mypy
    about them via --always-true and --always-false, see tox.ini.
    """
    global INFO, USE_PYQT5, USE_PYQT6, USE_PYSIDE6, IS_QT5, IS_QT6, \
        IS_PYQT, IS_PYSIDE, _initialized

    assert info.wrapper is not None, info
    assert not _initialized

    _initialized = True
    INFO = info
    USE_PYQT5 = info.wrapper == "PyQt5"
    USE_PYQT6 = info.wrapper == "PyQt6"
    USE_PYSIDE6 = info.wrapper == "PySide6"
    assert USE_PYQT5 + USE_PYQT6 + USE_PYSIDE6 == 1

    IS_QT5 = USE_PYQT5
    IS_QT6 = USE_PYQT6 or USE_PYSIDE6
    IS_PYQT = USE_PYQT5 or USE_PYQT6
    IS_PYSIDE = USE_PYSIDE6
    assert IS_QT5 ^ IS_QT6
    assert IS_PYQT ^ IS_PYSIDE


def init_implicit() -> None:
    """Initialize Qt wrapper globals implicitly at Qt import time.

    This gets called when any qutebrowser.qt module is imported, and implicitly
    initializes the Qt wrapper globals.

    After this is called, no explicit initialization via machinery.init() is possible
    anymore - thus, this should never be called before init() when running qutebrowser
    as an application (and any further calls will be a no-op).

    However, this ensures that any qutebrowser module can be imported without
    having to worry about machinery.init().  This is useful for e.g. tests or
    manual interactive usage of the qutebrowser code.
    """
    if _initialized:
        # Implicit initialization can happen multiple times
        # (all subsequent calls are a no-op)
        return

    info = _select_wrapper(args=None)
    if info.wrapper is None:
        raise NoWrapperAvailableError(info)

    _set_globals(info)


def init(args: argparse.Namespace) -> SelectionInfo:
    """Initialize Qt wrapper globals during qutebrowser application start.

    This gets called from earlyinit.py, i.e. after we have an argument parser,
    but before any kinds of Qt usage. This allows `args` to be passed, which is
    used to select the Qt wrapper (if --qt-wrapper is given).

    If any qutebrowser.qt module is imported before this, init_implicit() will be called
    instead, which means this can't be called anymore.
    """
    if _initialized:
        raise Error("init() already called before application init")

    info = _select_wrapper(args)
    if info.wrapper is not None:
        _set_globals(info)

    # If info is None here (no Qt wrapper available), we'll show an error later
    # in earlyinit.py.

    return info
