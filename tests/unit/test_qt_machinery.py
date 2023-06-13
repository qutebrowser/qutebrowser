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
from typing import Any, Optional, Dict, List

import pytest

from qutebrowser.qt import machinery


def test_unavailable_is_importerror():
    with pytest.raises(ImportError):
        raise machinery.Unavailable()


@pytest.fixture
def modules():
    """Return a dict of modules to import-patch, all unavailable by default."""
    return dict.fromkeys(machinery.WRAPPERS, False)


def test_autoselect_none_available(
    stubs: Any,
    modules: Dict[str, bool],
    monkeypatch: pytest.MonkeyPatch,
):
    stubs.ImportFake(modules, monkeypatch).patch()

    message = "No Qt wrapper found, tried PyQt6, PyQt5"
    with pytest.raises(machinery.Error, match=message):
        machinery._autoselect_wrapper()


@pytest.mark.parametrize(
    "available, expected",
    [
        (["PyQt6"], "PyQt6"),
        (["PyQt5"], "PyQt5"),
        (["PyQt5", "PyQt6"], "PyQt6"),
    ],
)
def test_autoselect(
    stubs: Any,
    modules: Dict[str, bool],
    available: List[str],
    expected: str,
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
        (None, None, "PyQt5"),
        (argparse.Namespace(qt_wrapper=None), None, "PyQt5"),
        # Only argument given
        (argparse.Namespace(qt_wrapper="PyQt6"), None, "PyQt6"),
        (argparse.Namespace(qt_wrapper="PyQt5"), None, "PyQt5"),
        # Only environment variable given
        (None, "PyQt6", "PyQt6"),
        (None, "PyQt5", "PyQt5"),
        # Both given
        (argparse.Namespace(qt_wrapper="PyQt5"), "PyQt6", "PyQt5"),
        (argparse.Namespace(qt_wrapper="PyQt6"), "PyQt5", "PyQt6"),
        (argparse.Namespace(qt_wrapper="PyQt6"), "PyQt6", "PyQt6"),
    ],
)
def test_select_wrapper(
    args: Optional[argparse.Namespace],
    env: Optional[str],
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
):
    if env is None:
        monkeypatch.delenv("QUTE_QT_WRAPPER", raising=False)
    else:
        monkeypatch.setenv("QUTE_QT_WRAPPER", env)

    assert machinery._select_wrapper(args) == expected


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


@pytest.mark.parametrize(
    "selected_wrapper, true_vars",
    [
        ("PyQt6", ["USE_PYQT6", "IS_QT6", "IS_PYQT"]),
        ("PyQt5", ["USE_PYQT5", "IS_QT5", "IS_PYQT"]),
        ("PySide6", ["USE_PYSIDE6", "IS_QT6", "IS_PYSIDE"]),
    ],
)
def test_init_properly(
    monkeypatch: pytest.MonkeyPatch, selected_wrapper: str, true_vars: str
):
    for wrapper in machinery.WRAPPERS:
        monkeypatch.delitem(sys.modules, wrapper, raising=False)

    monkeypatch.setattr(machinery, "_initialized", False)

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

    info = machinery.SelectionInfo(wrapper=selected_wrapper, reason="fake")
    monkeypatch.setattr(machinery, "_select_wrapper", lambda args: info)

    machinery.init()
    assert machinery.INFO == info

    expected_vars = dict.fromkeys(bool_vars, False)
    expected_vars.update(dict.fromkeys(true_vars, True))
    actual_vars = {var: getattr(machinery, var) for var in bool_vars}

    assert expected_vars == actual_vars
