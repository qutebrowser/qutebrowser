import os
import sys

from PyQt5.QtCore import (QT_VERSION_STR, PYQT_VERSION_STR, qVersion,
                          QStandardPaths, QCoreApplication)


def print_header():
    print("Python {}".format(sys.version))
    print("os.name: {}".format(os.name))
    print("sys.platform: {}".format(sys.platform))
    print()

    print("Qt {}, compiled {}".format(qVersion(), QT_VERSION_STR))
    print("PyQt {}".format(PYQT_VERSION_STR))
    print()


def print_paths():
    for name, obj in vars(QStandardPaths).items():
        if isinstance(obj, QStandardPaths.StandardLocation):
            print("{:25} {}".format(name, QStandardPaths.writableLocation(obj)))


def main():
    print_header()

    print("No QApplication")
    print("===============")
    print()
    print_paths()

    app = QCoreApplication(sys.argv)
    app.setApplicationName("qapp_name")

    print()
    print("With QApplication")
    print("=================")
    print()
    print_paths()


if __name__ == '__main__':
    main()
