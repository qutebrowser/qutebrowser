#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Show various QStandardPath paths."""

import os
import sys

from PyQt6.QtCore import (QT_VERSION_STR, PYQT_VERSION_STR, qVersion,
                          QStandardPaths, QCoreApplication)


def print_header():
    """Show system information."""
    print("Python {}".format(sys.version))
    print("os.name: {}".format(os.name))
    print("sys.platform: {}".format(sys.platform))
    print()

    print("Qt {}, compiled {}".format(qVersion(), QT_VERSION_STR))
    print("PyQt {}".format(PYQT_VERSION_STR))
    print()


def print_paths():
    """Print all QStandardPaths.StandardLocation members."""
    for name, obj in vars(QStandardPaths).items():
        if isinstance(obj, QStandardPaths.StandardLocation):
            location = QStandardPaths.writableLocation(obj)
            print("{:25} {}".format(name, location))


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
