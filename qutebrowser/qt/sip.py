from qutebrowser.qt import machinery

# While upstream recommends using PyQt6.sip ever since PyQt6 5.11, some distributions
# still package later versions of PyQt6 with a top-level "sip" rather than "PyQt6.sip".

if machinery.use_pyqt5:
    try:
        from PyQt5.sip import *
    except ImportError:
        from sip import *
elif machinery.use_pyqt6:
    try:
        from PyQt6.sip import *
    except ImportError:
        from sip import *
elif machinery.use_pyside2:
    raise machinery.Unavailable()
elif machinery.use_pyside6:
    raise machinery.Unavailable()
else:
    raise machinery.UnknownWrapper()
