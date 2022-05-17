# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# FIXME:qt6
# pylint: disable=missing-module-docstring,import-error,wildcard-import,unused-wildcard-import
# flake8: noqa

from qutebrowser.qt import machinery


if machinery.USE_PYQT5:
    from PyQt5.QtTest import *
elif machinery.USE_PYQT6:
    from PyQt6.QtTest import *
elif machinery.USE_PYSIDE2:
    from PySide2.QtTest import *
elif machinery.USE_PYSIDE6:
    from PySide6.QtTest import *
