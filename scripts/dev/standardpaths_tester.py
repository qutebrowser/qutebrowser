import os
import sys

from PyQt5.QtCore import (QT_VERSION_STR, PYQT_VERSION_STR, qVersion,
                          QStandardPaths)

print("Python {}".format(sys.version))
print("os.name: {}".format(os.name))
print("sys.platform: {}".format(sys.platform))
print()

print("Qt {}, compiled {}".format(qVersion(), QT_VERSION_STR))
print("PyQt {}".format(PYQT_VERSION_STR))
print()

for name, obj in vars(QStandardPaths).items():
    if isinstance(obj, QStandardPaths.StandardLocation):
        print("{:25} {}".format(name, QStandardPaths.writableLocation(obj)))
