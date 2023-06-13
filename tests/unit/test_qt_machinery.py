# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Test qutebrowser.qt.machinery."""

import sys
import argparse
import typing
from typing import Any, Optional, Dict, List, Type

import pytest

from qutebrowser.qt import machinery


@pytest.mark.parametrize(
    "exception",
    [
        machinery.Unavailable(),
        machinery.NoWrapperAvailableError(machinery.SelectionInfo()),
    ],
)
def test_importerror_exceptions(exception: Exception):
    with pytest.raises(ImportError):
        raise exception


def test_selectioninfo_set_module():
    info = machinery.SelectionInfo()
    info.set_module("PyQt5", "ImportError: Python imploded")
    assert info == machinery.SelectionInfo(
        wrapper=None,
        reason=machinery.SelectionReason.unknown,
        pyqt5="ImportError: Python imploded",
        pyqt6=None,
    )


@pytest.mark.parametrize(
    "info, expected",
    [
        (
            machinery.SelectionInfo(
                wrapper="PyQt5",
                reason=machinery.SelectionReason.cli,
            ),
            "Qt wrapper: PyQt5 (via --qt-wrapper)",
        ),
        (
            machinery.SelectionInfo(
                wrapper="PyQt6",
                reason=machinery.SelectionReason.env,
            ),
            "Qt wrapper: PyQt6 (via QUTE_QT_WRAPPER)",
        ),
        (
            machinery.SelectionInfo(
                wrapper="PyQt6",
                reason=machinery.SelectionReason.auto,
                pyqt5="ImportError: Python imploded",
                pyqt6="success",
            ),
            (
                "Qt wrapper info:\n"
                "PyQt5: ImportError: Python imploded\n"
                "PyQt6: success\n"
                "selected: PyQt6 (via autoselect)"
            )
        ),
    ])
def test_selectioninfo_str(info: machinery.SelectionInfo, expected: str):
    assert str(info) == expected


@pytest.fixture
def modules():
    """Return a dict of modules to import-patch, all unavailable by default."""
    return dict.fromkeys(machinery.WRAPPERS, False)


@pytest.mark.parametrize(
    "available, expected",
    [
        (
            [],
            machinery.SelectionInfo(
                wrapper=None,
                reason=machinery.SelectionReason.auto,
                pyqt6="ImportError: Fake ImportError for PyQt6.",
                pyqt5="ImportError: Fake ImportError for PyQt5.",
            ),
        ),
        (
            ["PyQt6"],
            machinery.SelectionInfo(
                wrapper="PyQt6", reason=machinery.SelectionReason.auto, pyqt6="success"
            ),
        ),
        (
            ["PyQt5"],
            machinery.SelectionInfo(
                wrapper="PyQt5",
                reason=machinery.SelectionReason.auto,
                pyqt6="ImportError: Fake ImportError for PyQt6.",
                pyqt5="success",
            ),
        ),
        (
            ["PyQt5", "PyQt6"],
            machinery.SelectionInfo(
                wrapper="PyQt6",
                reason=machinery.SelectionReason.auto,
                pyqt6="success",
                pyqt5=None,
            ),
        ),
    ],
)
def test_autoselect(
    stubs: Any,
    modules: Dict[str, bool],
    available: List[str],
    expected: machinery.SelectionInfo,
    monkeypatch: pytest.MonkeyPatch,
):
    for wrapper in available:
        modules[wrapper] = True
    stubs.ImportFake(modules, monkeypatch).patch()
    assert machinery._autoselect_wrapper() == expected


@pytest.mark.parametrize(
    "args, env, expected",
    [
        # Defaults with no overrides
        (
            None,
            None,
            machinery.SelectionInfo(
                wrapper="PyQt5", reason=machinery.SelectionReason.default
            ),
        ),
        (
            argparse.Namespace(qt_wrapper=None),
            None,
            machinery.SelectionInfo(
                wrapper="PyQt5", reason=machinery.SelectionReason.default
            ),
        ),
        (
            argparse.Namespace(qt_wrapper=None),
            "",
            machinery.SelectionInfo(
                wrapper="PyQt5", reason=machinery.SelectionReason.default
            ),
        ),
        # Only argument given
        (
            argparse.Namespace(qt_wrapper="PyQt6"),
            None,
            machinery.SelectionInfo(
                wrapper="PyQt6", reason=machinery.SelectionReason.cli
            ),
        ),
        (
            argparse.Namespace(qt_wrapper="PyQt5"),
            None,
            machinery.SelectionInfo(
                wrapper="PyQt5", reason=machinery.SelectionReason.cli
            ),
        ),
        (
            argparse.Namespace(qt_wrapper="PyQt5"),
            "",
            machinery.SelectionInfo(
                wrapper="PyQt5", reason=machinery.SelectionReason.cli
            ),
        ),
        # Only environment variable given
        (
            None,
            "PyQt6",
            machinery.SelectionInfo(
                wrapper="PyQt6", reason=machinery.SelectionReason.env
            ),
        ),
        (
            None,
            "PyQt5",
            machinery.SelectionInfo(
                wrapper="PyQt5", reason=machinery.SelectionReason.env
            ),
        ),
        # Both given
        (
            argparse.Namespace(qt_wrapper="PyQt5"),
            "PyQt6",
            machinery.SelectionInfo(
                wrapper="PyQt5", reason=machinery.SelectionReason.cli
            ),
        ),
        (
            argparse.Namespace(qt_wrapper="PyQt6"),
            "PyQt5",
            machinery.SelectionInfo(
                wrapper="PyQt6", reason=machinery.SelectionReason.cli
            ),
        ),
        (
            argparse.Namespace(qt_wrapper="PyQt6"),
            "PyQt6",
            machinery.SelectionInfo(
                wrapper="PyQt6", reason=machinery.SelectionReason.cli
            ),
        ),
    ],
)
def test_select_wrapper(
    args: Optional[argparse.Namespace],
    env: Optional[str],
    expected: machinery.SelectionInfo,
    monkeypatch: pytest.MonkeyPatch,
):
    if env is None:
        monkeypatch.delenv("QUTE_QT_WRAPPER", raising=False)
    else:
        monkeypatch.setenv("QUTE_QT_WRAPPER", env)

    assert machinery._select_wrapper(args) == expected


@pytest.fixture
def undo_init(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend Qt support isn't initialized yet and Qt was never imported."""
    for wrapper in machinery.WRAPPERS:
        monkeypatch.delitem(sys.modules, wrapper, raising=False)
    monkeypatch.setattr(machinery, "_initialized", False)
    monkeypatch.delenv("QUTE_QT_WRAPPER", raising=False)


def test_init_multiple_implicit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(machinery, "_initialized", True)
    machinery.init()
    machinery.init()


def test_init_multiple_explicit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(machinery, "_initialized", True)
    machinery.init()

    with pytest.raises(
        machinery.Error, match=r"init\(\) already called before application init"
    ):
        machinery.init(args=argparse.Namespace(qt_wrapper="PyQt6"))


def test_init_after_qt_import(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(machinery, "_initialized", False)
    with pytest.raises(machinery.Error, match="Py.* already imported"):
        machinery.init()


@pytest.mark.xfail(reason="autodetect not used yet")
def test_init_none_available_implicit(
    stubs: Any,
    modules: Dict[str, bool],
    monkeypatch: pytest.MonkeyPatch,
    undo_init: None,
):
    stubs.ImportFake(modules, monkeypatch).patch()
    message = "No Qt wrapper was importable."  # FIXME maybe check info too
    with pytest.raises(machinery.NoWrapperAvailableError, match=message):
        machinery.init(args=None)


@pytest.mark.xfail(reason="autodetect not used yet")
def test_init_none_available_explicit(
    stubs: Any,
    modules: Dict[str, bool],
    monkeypatch: pytest.MonkeyPatch,
    undo_init: None,
):
    stubs.ImportFake(modules, monkeypatch).patch()
    info = machinery.init(args=argparse.Namespace(qt_wrapper=None))
    assert info == machinery.SelectionInfo(
        wrapper=None,
        reason=machinery.SelectionReason.default,
        pyqt6="ImportError: Fake ImportError for PyQt6.",
        pyqt5="ImportError: Fake ImportError for PyQt5.",
    )


@pytest.mark.parametrize(
    "selected_wrapper, true_vars",
    [
        ("PyQt6", ["USE_PYQT6", "IS_QT6", "IS_PYQT"]),
        ("PyQt5", ["USE_PYQT5", "IS_QT5", "IS_PYQT"]),
        ("PySide6", ["USE_PYSIDE6", "IS_QT6", "IS_PYSIDE"]),
    ],
)
def test_init_properly(
    monkeypatch: pytest.MonkeyPatch,
    selected_wrapper: str,
    true_vars: str,
    undo_init: None,
):
    bool_vars = [
        "USE_PYQT5",
        "USE_PYQT6",
        "USE_PYSIDE6",
        "IS_QT5",
        "IS_QT6",
        "IS_PYQT",
        "IS_PYSIDE",
    ]
    all_vars = bool_vars + ["INFO"]
    # Make sure we didn't forget anything that's declared in the module.
    # Not sure if this is a good idea. Might remove it in the future if it breaks.
    assert set(typing.get_type_hints(machinery).keys()) == set(all_vars)

    for var in all_vars:
        monkeypatch.delattr(machinery, var)

    info = machinery.SelectionInfo(
        wrapper=selected_wrapper,
        reason=machinery.SelectionReason.fake,
    )
    monkeypatch.setattr(machinery, "_select_wrapper", lambda args: info)

    machinery.init()
    assert machinery.INFO == info

    expected_vars = dict.fromkeys(bool_vars, False)
    expected_vars.update(dict.fromkeys(true_vars, True))
    actual_vars = {var: getattr(machinery, var) for var in bool_vars}

    assert expected_vars == actual_vars
