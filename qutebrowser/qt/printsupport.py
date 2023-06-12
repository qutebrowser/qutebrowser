# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# FIXME:qt6 (lint)
# pylint: disable=missing-module-docstring,import-error,wildcard-import,unused-wildcard-import
# flake8: noqa

from qutebrowser.qt import machinery

machinery.init()


if machinery.USE_PYSIDE6:
    from PySide6.QtPrintSupport import *
elif machinery.USE_PYQT5:
    from PyQt5.QtPrintSupport import *
elif machinery.USE_PYQT6:
    from PyQt6.QtPrintSupport import *
else:
    raise machinery.UnknownWrapper()
