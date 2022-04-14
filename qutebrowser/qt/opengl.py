from qutebrowser.qt import machinery


if machinery.USE_PYQT5:
    from PyQt5.QtGui import QOpenGLVersionProfile
elif machinery.USE_PYQT6:
    from PyQt6.QtOpenGL import *
elif machinery.USE_PYSIDE2:
    from PySide2.QtGui import QOpenGLVersionProfile
elif machinery.USE_PYSIDE6:
    from PySide6.QtOpenGL import *
else:
    raise machinery.UnknownWrapper()
