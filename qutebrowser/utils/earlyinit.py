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

"""Things which need to be done really early (e.g. before importing Qt)."""

import os
import sys


def check_python_version():
    """Check if correct python version is run."""
    if sys.hexversion < 0x03030000:
        print("Fatal error: At least Python 3.3 is required to run "
              "qutebrowser, but {} is installed!".format(
                  '.'.join(map(str, sys.version_info[:3]))))
        sys.exit(1)


def init_faulthandler():
    """Enable faulthandler module if available.

    This print a nice traceback on segfauls. It's only available on Python
    3.3+, but if it's unavailable, it doesn't matter much (we just ignore
    that).
    """

    try:
        import faulthandler  # pylint: disable=import-error
    except ImportError:
        return
    if sys.__stdout__ is not None:
        # When run with pythonw.exe, sys.__stdout__ can be None:
        # https://docs.python.org/3/library/sys.html#sys.__stdout__
        # If we'd enable faulthandler in that case, we just get a weird
        # exception, so we don't enable faulthandler in that case.
        #
        # FIXME at the point we have our config/data dirs, we probably should
        # re-enable faulthandler to write to a file. Then we can also display
        # crashes to the user at the next start.
        return
    faulthandler.enable()
    if hasattr(faulthandler, 'register'):
        # If available, we also want a traceback on SIGUSR1.
        from signal import SIGUSR1
        faulthandler.register(SIGUSR1)


def fix_harfbuzz():
    """Fix harfbuzz issues.

    This switches to an older (but more stable) harfbuzz font rendering engine
    instead of using the system wide one.

    This fixes crashes on various sites.
    See https://bugreports.qt-project.org/browse/QTBUG-36099
    """
    if sys.platform.startswith('linux'):
        # Switch to old but stable font rendering engine
        os.environ['QT_HARFBUZZ'] = 'old'


def check_pyqt_core():
    """Check if PyQt core is installed."""
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


def check_pyqt_webkit():
    """Check if PyQt WebKit is installed."""
    # At this point we can rely on QtCore being available, so we can display an
    # error dialog
    try:
        import PyQt5.QtWebKit
    except ImportError:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        import textwrap
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
