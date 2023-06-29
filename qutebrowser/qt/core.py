# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# pylint: disable=import-error,wildcard-import,unused-wildcard-import

"""Wrapped Qt imports for Qt Core.

All code in qutebrowser should use this module instead of importing from
PyQt/PySide directly. This allows supporting both Qt 5 and Qt 6.

See machinery.py for details on how Qt wrapper selection works.

Any API exported from this module is based on the Qt 6 API:
https://doc.qt.io/qt-6/qtcore-index.html
"""

from typing import TYPE_CHECKING
from qutebrowser.qt import machinery

machinery.init_implicit()


if machinery.USE_PYSIDE6:
    from PySide6.QtCore import *
elif machinery.USE_PYQT5:
    from PyQt5.QtCore import *
elif machinery.USE_PYQT6:
    from PyQt6.QtCore import *

    if TYPE_CHECKING:
        # FIXME:mypy PyQt6-stubs issue
        # WORKAROUND for missing pyqtProperty typing, ported from PyQt5-stubs:
        # https://github.com/python-qt-tools/PyQt5-stubs/blob/5.15.6.0/PyQt5-stubs/QtCore.pyi#L70-L111
        import typing

        TPropertyTypeVal = typing.TypeVar('TPropertyTypeVal')

        TPropGetter = typing.TypeVar('TPropGetter', bound=typing.Callable[[QObjectT], TPropertyTypeVal])
        TPropSetter = typing.TypeVar('TPropSetter', bound=typing.Callable[[QObjectT, TPropertyTypeVal], None])
        TPropDeleter = typing.TypeVar('TPropDeleter', bound=typing.Callable[[QObjectT], None])
        TPropResetter = typing.TypeVar('TPropResetter', bound=typing.Callable[[QObjectT], None])

        class pyqtProperty:
            def __init__(
                self,
                type: typing.Union[type, str],
                fget: typing.Optional[
                    typing.Callable[[QObjectT], TPropertyTypeVal]
                ] = None,
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

else:
    raise machinery.UnknownWrapper()
