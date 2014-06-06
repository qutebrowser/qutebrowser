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

"""Things which need to be done really early (e.g. before importing Qt).

At this point we can be sure we have all python 3.3 features available.
"""

import os
import sys
import faulthandler
import textwrap
import traceback
import signal


# Now we initialize the faulthandler as early as possible, so we theoretically
# could catch segfaults occuring later.
def init_faulthandler():
    """Enable faulthandler module if available.

    This print a nice traceback on segfauls.
    """
    if sys.stderr is None:
        # When run with pythonw.exe, sys.stderr can be None:
        # https://docs.python.org/3/library/sys.html#sys.__stderr__
        # If we'd enable faulthandler in that case, we just get a weird
        # exception, so we don't enable faulthandler if we have no stdout.
        #
        # Later when we have our data dir available we re-enable faulthandler
        # to write to a file so we can display a crash to the user at the next
        # start.
        return
    faulthandler.enable()
    if hasattr(faulthandler, 'register') and hasattr(signal, 'SIGUSR1'):
        # If available, we also want a traceback on SIGUSR1.
        faulthandler.register(signal.SIGUSR1)  # pylint: disable=no-member


# Now the faulthandler is enabled we fix the Qt harfbuzzing library, before
# importing any Qt stuff.
def fix_harfbuzz(args):
    """Fix harfbuzz issues.

    This switches to an older (but more stable) harfbuzz font rendering engine
    instead of using the system wide one.

    This fixes crashes on various sites.
    See https://bugreports.qt-project.org/browse/QTBUG-36099

    IMPORTANT: This needs to be done before QWidgets is imported in any way!

    Args:
        args: The argparse namespace.
    """
    from qutebrowser.utils.log import init as logger
    from PyQt5.QtCore import qVersion
    if 'PyQt5.QtWidgets' in sys.modules:
        logger.warning("Harfbuzz fix attempted but QtWidgets is already "
                       "imported!")
    if sys.platform.startswith('linux') and args.harfbuzz == 'auto':
        # Lets use the most stable variant.
        #
        # - On Qt 5.2 (and probably earlier) the new engine probably has more
        #   crashes and is also experimental.
        #
        # - On Qt 5.3.0 there's a bug that affects a lot of websites:
        #   https://bugreports.qt-project.org/browse/QTBUG-39278
        #   So the new engine will be more stable.
        #
        # - On Qt 5.3.1 this bug hopefully will be fixed and the old engine
        #   will be the more stable one again.
        if qVersion() == '5.3.0':
            logger.debug("Using new harfbuzz engine (auto)")
            os.environ['QT_HARFBUZZ'] = 'new'
        else:
            logger.debug("Using old harfbuzz engine (auto)")
            os.environ['QT_HARFBUZZ'] = 'old'
    elif args.harfbuzz in ('old', 'new'):
        # forced harfbuzz variant
        # FIXME looking at the Qt code, 'new' isn't a valid value, but leaving
        # it empty and using new yields different behaviour...
        logger.debug("Using {} harfbuzz engine (forced)".format(args.harfbuzz))
        os.environ['QT_HARFBUZZ'] = args.harfbuzz
    else:
        # use system default harfbuzz
        logger.debug("Using system harfbuzz engine")


# At this point we can safely import Qt stuff, but we can't be sure it's
# actually available.
# Here we check if QtCore is available, and if not, print a message to the
# console.
def check_pyqt_core():
    """Check if PyQt core is installed."""
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
            """).strip(), file=sys.stderr)
        if '--debug' in sys.argv:
            print(file=sys.stderr)
            traceback.print_exc()
        sys.exit(1)


# Now we can be sure QtCore is available, so we can print dialogs on errors, so
# people only using the GUI notice them as well.
def check_pyqt_webkit():
    """Check if PyQt WebKit is installed."""
    from PyQt5.QtWidgets import QApplication, QMessageBox
    try:
        import PyQt5.QtWebKit  # pylint: disable=unused-variable
    except ImportError:
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
            print(file=sys.stderr)
            traceback.print_exc()
        msgbox.resize(msgbox.sizeHint())
        msgbox.exec_()
        app.quit()
        sys.exit(1)
