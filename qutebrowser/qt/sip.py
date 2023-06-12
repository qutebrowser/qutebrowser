# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# pylint: disable=import-error,wildcard-import,unused-wildcard-import

"""Wrapped Qt imports for PyQt5.sip/PyQt6.sip.

All code in qutebrowser should use this module instead of importing from
PyQt/sip directly. This allows supporting both Qt 5 and Qt 6.

See machinery.py for details on how Qt wrapper selection works.

Any API exported from this module is based on the PyQt6.sip API:
https://www.riverbankcomputing.com/static/Docs/PyQt6/api/sip/sip-module.html

Note that we don't yet abstract between PySide/PyQt here.
"""

from qutebrowser.qt import machinery

machinery.init()

# While upstream recommends using PyQt6.sip ever since PyQt6 5.11, some distributions
# still package later versions of PyQt6 with a top-level "sip" rather than "PyQt6.sip".
_VENDORED_SIP = False

if machinery.USE_PYSIDE6:  # pylint: disable=no-else-raise
    raise machinery.Unavailable()
elif machinery.USE_PYQT5:
    try:
        from PyQt5.sip import *
        _VENDORED_SIP = True
    except ImportError:
        pass
elif machinery.USE_PYQT6:
    try:
        from PyQt6.sip import *
        _VENDORED_SIP = True
    except ImportError:
        pass
else:
    raise machinery.UnknownWrapper()

if not _VENDORED_SIP:
    from sip import *  # type: ignore[import]
