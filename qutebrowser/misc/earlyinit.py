# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

At this point we can be sure we have all python 3.4 features available.
"""

try:
    # Importing hunter to register its atexit handler early so it gets called
    # late.
    import hunter  # pylint: disable=import-error,unused-import
except ImportError:
    hunter = None

import os
import sys
import faulthandler
import traceback
import signal
import operator
import importlib
try:
    import tkinter  # pylint: disable=import-error
except ImportError:
    tkinter = None
# NOTE: No qutebrowser or PyQt import should be done here, as some early
# initialization needs to take place before that!


def _missing_str(name, *, windows=None, pip=None):
    """Get an error string for missing packages.

    Args:
        name: The name of the package.
        windows: String to be displayed for Windows.
        pip: pypi package name.
    """
    blocks = ["Fatal error: <b>{}</b> is required to run qutebrowser but "
              "could not be imported! Maybe it's not installed?".format(name)]
    lines = ['Please search for the python3 version of {} in your '
             'distributions packages, or install it via pip.'.format(name)]
    blocks.append('<br />'.join(lines))
    lines = ['<b>If you installed a qutebrowser package for your '
             'distribution, please report this as a bug.</b>']
    blocks.append('<br />'.join(lines))
    if windows is not None:
        lines = ["<b>On Windows:</b>"]
        lines += windows.splitlines()
        blocks.append('<br />'.join(lines))
    if pip is not None:
        lines = ["<b>Using pip:</b>"]
        lines.append("pip3 install {}".format(pip))
        blocks.append('<br />'.join(lines))
    return '<br /><br />'.join(blocks)


def _die(message, exception=None):
    """Display an error message using Qt and quit.

    We import the imports here as we want to do other stuff before the imports.

    Args:
        message: The message to display.
        exception: The exception object if we're handling an exception.
    """
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import Qt
    if (('--debug' in sys.argv or '--no-err-windows' in sys.argv) and
            exception is not None):
        print(file=sys.stderr)
        traceback.print_exc()
    app = QApplication(sys.argv)
    if '--no-err-windows' in sys.argv:
        print(message, file=sys.stderr)
        print("Exiting because of --no-err-windows.", file=sys.stderr)
    else:
        message += '<br/><br/><br/><b>Error:</b><br/>{}'.format(exception)
        msgbox = QMessageBox(QMessageBox.Critical, "qutebrowser: Fatal error!",
                             message)
        msgbox.setTextFormat(Qt.RichText)
        msgbox.resize(msgbox.sizeHint())
        msgbox.exec_()
    app.quit()
    sys.exit(1)


def init_faulthandler(fileobj=sys.__stderr__):
    """Enable faulthandler module if available.

    This print a nice traceback on segfaults.

    We use sys.__stderr__ instead of sys.stderr here so this will still work
    when sys.stderr got replaced, e.g. by "Python Tools for Visual Studio".

    Args:
        fobj: An opened file object to write the traceback to.
    """
    if fileobj is None:
        # When run with pythonw.exe, sys.__stderr__ can be None:
        # https://docs.python.org/3/library/sys.html#sys.__stderr__
        # If we'd enable faulthandler in that case, we just get a weird
        # exception, so we don't enable faulthandler if we have no stdout.
        #
        # Later when we have our data dir available we re-enable faulthandler
        # to write to a file so we can display a crash to the user at the next
        # start.
        return
    faulthandler.enable(fileobj)
    if hasattr(faulthandler, 'register') and hasattr(signal, 'SIGUSR1'):
        # If available, we also want a traceback on SIGUSR1.
        faulthandler.register(signal.SIGUSR1)  # pylint: disable=no-member


def fix_harfbuzz(args):
    """Fix harfbuzz issues.

    This switches to the most stable harfbuzz font rendering engine available
    on the platform instead of using the system wide one.

    This fixes crashes on various sites.

    - On Qt 5.2 (and probably earlier) the new engine probably has more
      crashes and is also experimental.

      e.g. https://bugreports.qt.io/browse/QTBUG-36099

    - On Qt 5.3.0 there's a bug that affects a lot of websites:
      https://bugreports.qt.io/browse/QTBUG-39278
      So the new engine will be more stable.

    - On Qt 5.3.1 this bug is fixed and the old engine will be the more stable
      one again.

    IMPORTANT: This needs to be done before QWidgets is imported in any way!

    WORKAROUND (remove this when we bump the requirements to 5.3.1)

    Args:
        args: The argparse namespace.
    """
    from qutebrowser.utils import log
    from PyQt5.QtCore import qVersion
    if 'PyQt5.QtWidgets' in sys.modules:
        log.init.warning("Harfbuzz fix attempted but QtWidgets is already "
                         "imported!")
    if sys.platform.startswith('linux') and args.harfbuzz == 'auto':
        if qVersion() == '5.3.0':
            log.init.debug("Using new harfbuzz engine (auto)")
            os.environ['QT_HARFBUZZ'] = 'new'
        else:
            log.init.debug("Using old harfbuzz engine (auto)")
            os.environ['QT_HARFBUZZ'] = 'old'
    elif args.harfbuzz in ('old', 'new'):
        # forced harfbuzz variant
        # FIXME looking at the Qt code, 'new' isn't a valid value, but leaving
        # it empty and using new yields different behavior...
        # (probably irrelevant when workaround gets removed)
        log.init.debug("Using {} harfbuzz engine (forced)".format(
            args.harfbuzz))
        os.environ['QT_HARFBUZZ'] = args.harfbuzz
    else:
        log.init.debug("Using system harfbuzz engine")


def check_pyqt_core():
    """Check if PyQt core is installed."""
    try:
        import PyQt5.QtCore  # pylint: disable=unused-variable
    except ImportError as e:
        text = _missing_str('PyQt5',
                            windows="Use the installer by Riverbank computing "
                                    "or the standalone qutebrowser exe.<br />"
                                    "http://www.riverbankcomputing.co.uk/"
                                    "software/pyqt/download5")
        text = text.replace('<b>', '')
        text = text.replace('</b>', '')
        text = text.replace('<br />', '\n')
        text += '\n\nError: {}'.format(e)
        if tkinter and '--no-err-windows' not in sys.argv:
            root = tkinter.Tk()
            root.withdraw()
            tkinter.messagebox.showerror("qutebrowser: Fatal error!", text)
        else:
            print(text, file=sys.stderr)
        if '--debug' in sys.argv or '--no-err-windows' in sys.argv:
            print(file=sys.stderr)
            traceback.print_exc()
        sys.exit(1)


def check_qt_version():
    """Check if the Qt version is recent enough."""
    from PyQt5.QtCore import qVersion
    from qutebrowser.utils import qtutils
    if qtutils.version_check('5.2.0', operator.lt):
        text = ("Fatal error: Qt and PyQt >= 5.2.0 are required, but {} is "
                "installed.".format(qVersion()))
        _die(text)


def check_ssl_support():
    """Check if SSL support is available."""
    try:
        from PyQt5.QtNetwork import QSslSocket
    except ImportError:
        ok = False
    else:
        ok = QSslSocket.supportsSsl()
    if not ok:
        text = "Fatal error: Your Qt is built without SSL support."
        _die(text)


def check_libraries():
    """Check if all needed Python libraries are installed."""
    modules = {
        'PyQt5.QtWebKit': _missing_str("PyQt5.QtWebKit"),
        'pkg_resources':
            _missing_str("pkg_resources/setuptools",
                         windows="Run   python -m ensurepip."),
        'pypeg2':
            _missing_str("pypeg2",
                         pip="pypeg2"),
        'jinja2':
            _missing_str("jinja2",
                         windows="Install from http://www.lfd.uci.edu/"
                                 "~gohlke/pythonlibs/#jinja2 or via pip.",
                         pip="jinja2"),
        'pygments':
            _missing_str("pygments",
                         windows="Install from http://www.lfd.uci.edu/"
                                 "~gohlke/pythonlibs/#pygments or via pip.",
                         pip="pygments"),
        'yaml':
            _missing_str("PyYAML",
                         windows="Use the installers at "
                                 "http://pyyaml.org/download/pyyaml/ (py3.4) "
                                 "or Install via pip.",
                         pip="PyYAML"),
    }
    for name, text in modules.items():
        try:
            importlib.import_module(name)
        except ImportError as e:
            _die(text, e)


def remove_inputhook():
    """Remove the PyQt input hook.

    Doing this means we can't use the interactive shell anymore (which we don't
    anyways), but we can use pdb instead."""
    from PyQt5.QtCore import pyqtRemoveInputHook
    pyqtRemoveInputHook()


def init_log(args):
    """Initialize logging.

    Args:
        args: The argparse namespace.
    """
    from qutebrowser.utils import log
    log.init_log(args)
    log.init.debug("Log initialized.")


def earlyinit(args):
    """Do all needed early initialization.

    Note that it's vital the other earlyinit functions get called in the right
    order!

    Args:
        args: The argparse namespace.
    """
    # First we initialize the faulthandler as early as possible, so we
    # theoretically could catch segfaults occurring later during earlyinit.
    init_faulthandler()
    # Here we check if QtCore is available, and if not, print a message to the
    # console or via Tk.
    check_pyqt_core()
    # Now the faulthandler is enabled we fix the Qt harfbuzzing library, before
    # importing QtWidgets.
    fix_harfbuzz(args)
    # Now we can be sure QtCore is available, so we can print dialogs on
    # errors, so people only using the GUI notice them as well.
    check_qt_version()
    check_ssl_support()
    remove_inputhook()
    check_libraries()
    init_log(args)
