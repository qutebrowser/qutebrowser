# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Check if everything needed for qutebrowser is there.

In a separate file because this needs to be done early before any imports.
"""

import sys


def check():
    """Check if all dependencies are met."""
    if sys.hexversion < 0x03030000:
        print("Fatal error: At least Python 3.3 is required to run "
              "qutebrowser, but {} is installed!".format(
                  '.'.join(map(str, sys.version_info[:3]))))
        sys.exit(1)
    import textwrap
    try:
        import PyQt5.QtCore  # pylint: disable=unused-variable
    except ImportError:
        print(textwrap.dedent("""
            Fatal error: PyQt5 is required to run qutebrowser but could not
            be imported! Maybe it's not installed?

            On Debian:
                apt-get install python3-pyqt5 python3-pyqt5.qtwebkit

            On Archlinux:
                pacman -S python-pyqt5 qt5-webkit
                or install the qutebrowser package from AUR

            On Windows:
                Use the installer by Riverbank computing or the standalone
                qutebrowser exe.

                http://www.riverbankcomputing.co.uk/software/pyqt/download5

            For other distributions:
                Check your package manager for similiarly named packages.
            """).strip())
        if '--debug' in sys.argv:
            import traceback
            print()
            traceback.print_exc()
        sys.exit(1)
    # At this point we can rely on QtCore being available, so we can display an
    # error dialog
    try:
        import PyQt5.QtWebKit
    except ImportError:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        app = QApplication(sys.argv)
        msgbox = QMessageBox(QMessageBox.Critical, "qutebrowser: Fatal error!",
                             textwrap.dedent("""
            Fatal error: QtWebKit is required to run qutebrowser but could not
            be imported! Maybe it's not installed?

            On Debian:
                apt-get install python3-pyqt5.qtwebkit

            On Archlinux:
                pacman -S qt5-webkit

            For other distributions:
                Check your package manager for similiarly named packages.
            """).strip())
        if '--debug' in sys.argv:
            import traceback
            print()
            traceback.print_exc()
        msgbox.resize(msgbox.sizeHint())
        msgbox.exec_()
        app.quit()
    # At this point we have everything we need.
