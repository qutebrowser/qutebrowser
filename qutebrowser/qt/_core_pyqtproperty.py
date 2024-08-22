# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""WORKAROUND for missing pyqtProperty typing, ported from PyQt5-stubs:

FIXME:mypy PyQt6-stubs issue
https://github.com/python-qt-tools/PyQt5-stubs/blob/5.15.6.0/PyQt5-stubs/QtCore.pyi#L68-L111
"""

# flake8: noqa
# pylint: disable=invalid-name,missing-class-docstring,too-many-arguments,redefined-builtin,unused-argument

import typing
from PyQt6.QtCore import QObject, pyqtSignal

if typing.TYPE_CHECKING:
    QObjectT = typing.TypeVar("QObjectT", bound=QObject)

    TPropertyTypeVal = typing.TypeVar("TPropertyTypeVal")

    TPropGetter = typing.TypeVar(
        "TPropGetter", bound=typing.Callable[[QObjectT], TPropertyTypeVal]
    )
    TPropSetter = typing.TypeVar(
        "TPropSetter", bound=typing.Callable[[QObjectT, TPropertyTypeVal], None]
    )
    TPropDeleter = typing.TypeVar(
        "TPropDeleter", bound=typing.Callable[[QObjectT], None]
    )
    TPropResetter = typing.TypeVar(
        "TPropResetter", bound=typing.Callable[[QObjectT], None]
    )

    class pyqtProperty:
        def __init__(
            self,
            type: typing.Union[type, str],
            fget: typing.Optional[typing.Callable[[QObjectT], TPropertyTypeVal]] = None,
            fset: typing.Optional[
                typing.Callable[[QObjectT, TPropertyTypeVal], None]
            ] = None,
            freset: typing.Optional[typing.Callable[[QObjectT], None]] = None,
            fdel: typing.Optional[typing.Callable[[QObjectT], None]] = None,
            doc: typing.Optional[str] = "",
            designable: bool = True,
            scriptable: bool = True,
            stored: bool = True,
            user: bool = True,
            constant: bool = True,
            final: bool = True,
            notify: typing.Optional[pyqtSignal] = None,
            revision: int = 0,
        ) -> None:
            ...

        type: typing.Union[type, str]
        fget: typing.Optional[typing.Callable[[], TPropertyTypeVal]]
        fset: typing.Optional[typing.Callable[[TPropertyTypeVal], None]]
        freset: typing.Optional[typing.Callable[[], None]]
        fdel: typing.Optional[typing.Callable[[], None]]

        def read(self, func: TPropGetter) -> "pyqtProperty":
            ...

        def write(self, func: TPropSetter) -> "pyqtProperty":
            ...

        def reset(self, func: TPropResetter) -> "pyqtProperty":
            ...

        def getter(self, func: TPropGetter) -> "pyqtProperty":
            ...

        def setter(self, func: TPropSetter) -> "pyqtProperty":
            ...

        def deleter(self, func: TPropDeleter) -> "pyqtProperty":
            ...

        def __call__(self, func: TPropGetter) -> "pyqtProperty":
            ...
