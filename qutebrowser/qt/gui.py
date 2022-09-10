# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# FIXME:qt6 (lint)
# pylint: disable=missing-module-docstring,import-error,wildcard-import,unused-wildcard-import,unused-import
# flake8: noqa

from qutebrowser.qt import machinery


if machinery.USE_PYSIDE6:
    from PySide6.QtGui import *
elif machinery.USE_PYQT5:
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import QFileSystemModel
    del QOpenGLVersionProfile  # moved to QtOpenGL in Qt 6
elif machinery.USE_PYQT6:
    from PyQt6.QtGui import *
else:
    raise machinery.UnknownWrapper()
