from qutebrowser.qt import machinery


if machinery.use_pyqt5:
    from PyQt5.QtCore import *
    Signal = pyqtSignal
    Slot = pyqtSlot
elif machinery.use_pyqt6:
    from PyQt6.QtCore import *
    Signal = pyqtSignal
    Slot = pyqtSlot
elif machinery.use_pyside2:
    from PySide2.QtCore import *
elif machinery.use_pyside6:
    from PySide6.QtCore import *
else:
    raise machinery.UnknownWrapper()
