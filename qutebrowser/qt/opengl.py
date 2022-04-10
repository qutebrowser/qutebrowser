from qutebrowser.qt import machinery


if machinery.use_pyqt5:
    from PyQt5.QtGui import QOpenGLVersionProfile
elif machinery.use_pyqt6:
    from PyQt6.QtOpenGL import *
elif machinery.use_pyside2:
    from PySide2.QtGui import QOpenGLVersionProfile
elif machinery.use_pyside6:
    from PySide6.QtOpenGL import *
else:
    raise machinery.UnknownWrapper()
