# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# FIXME:qt6 (lint)
# pylint: disable=missing-module-docstring,wildcard-import,unused-wildcard-import,no-else-raise
# flake8: noqa

from qutebrowser.qt import machinery

# While upstream recommends using PyQt6.sip ever since PyQt6 5.11, some distributions
# still package later versions of PyQt6 with a top-level "sip" rather than "PyQt6.sip".

if machinery.USE_PYSIDE6:
    raise machinery.Unavailable()
elif machinery.USE_PYQT5:
    try:
        from PyQt5.sip import *
    except ImportError:
        from sip import *
elif machinery.USE_PYQT6:
    try:
        from PyQt6.sip import *
    except ImportError:
        from sip import *
else:
    raise machinery.UnknownWrapper()
