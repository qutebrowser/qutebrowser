# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# FIXME:qt6 (lint)
# pylint: disable=missing-module-docstring,import-error,wildcard-import,unused-wildcard-import
# flake8: noqa

from qutebrowser.qt import machinery

machinery.init()


if machinery.USE_PYSIDE6:
    from PySide6.QtWidgets import *
elif machinery.USE_PYQT5:
    from PyQt5.QtWidgets import *
elif machinery.USE_PYQT6:
    from PyQt6.QtWidgets import *
else:
    raise machinery.UnknownWrapper()

if machinery.IS_QT5:
    del QFileSystemModel  # moved to QtGui in Qt 6
