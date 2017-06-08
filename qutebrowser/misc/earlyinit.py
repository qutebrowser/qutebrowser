# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
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

"""Things which need to be done really early (e.g. before importing Qt).

At this point we can be sure we have all python 3.4 features available.
"""

try:
    # Importing hunter to register its atexit handler early so it gets called
    # late.
    import hunter  # pylint: disable=unused-import
except ImportError:
    hunter = None

import os
import sys
import faulthandler
import traceback
import signal
import importlib
import datetime
try:
    import tkinter
except ImportError:
    tkinter = None

import pkg_resources

# NOTE: No qutebrowser or PyQt import should be done here, as some early
# initialization needs to take place before that!


START_TIME = datetime.datetime.now()


def _missing_str(name, *, windows=None, pip=None, webengine=False):
    """Get an error string for missing packages.

    Args:
        name: The name of the package.
        windows: String to be displayed for Windows.
        pip: pypi package name.
        webengine: Whether this is checking the QtWebEngine package
    """
    blocks = ["Fatal error: <b>{}</b> is required to run qutebrowser but "
              "could not be imported! Maybe it's not installed?".format(name),
              "<b>The error encountered was:</b><br />%ERROR%"]
    lines = ['Please search for the python3 version of {} in your '
             'distributions packages, or install it via pip.'.format(name)]
    blocks.append('<br />'.join(lines))
    if not webengine:
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
        if exception is not None:
            message = message.replace('%ERROR%', str(exception))
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
    if (hasattr(faulthandler, 'register') and hasattr(signal, 'SIGUSR1') and
            sys.stderr is not None):
        # If available, we also want a traceback on SIGUSR1.
        # pylint: disable=no-member,useless-suppression
        faulthandler.register(signal.SIGUSR1)


def _qt_version():
    """Get the running Qt version.

    Needs to be in a function so we can do a local import easily (to not import
    from QtCore too early) but can patch this out easily for tests.
    """
    from PyQt5.QtCore import qVersion
    return pkg_resources.parse_version(qVersion())


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

    - On Qt 5.4 the new engine is the default and most bugs are taken care of.

    IMPORTANT: This needs to be done before QWidgets is imported in any way!

    WORKAROUND (remove this when we bump the requirements to 5.3.1)

    Args:
        args: The argparse namespace.
    """
    from qutebrowser.utils import log
    if 'PyQt5.QtWidgets' in sys.modules:
        msg = "Harfbuzz fix attempted but QtWidgets is already imported!"
        if getattr(sys, 'frozen', False):
            log.init.debug(msg)
        else:
            log.init.warning(msg)
    if sys.platform.startswith('linux') and args.harfbuzz == 'auto':
        if _qt_version() == pkg_resources.parse_version('5.3.0'):
            log.init.debug("Using new harfbuzz engine (auto)")
            os.environ['QT_HARFBUZZ'] = 'new'
        elif _qt_version() < pkg_resources.parse_version('5.4.0'):
            log.init.debug("Using old harfbuzz engine (auto)")
            os.environ['QT_HARFBUZZ'] = 'old'
        else:
            log.init.debug("Using system harfbuzz engine (auto)")
    elif args.harfbuzz in ['old', 'new']:
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
        text = text.replace('%ERROR%', str(e))
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


def get_backend(args):
    """Find out what backend to use based on available libraries.

    Note this function returns the backend as a string so we don't have to
    import qutebrowser.utils.usertypes yet.
    """
    try:
        import PyQt5.QtWebKit  # pylint: disable=unused-variable
        webkit_available = True
    except ImportError:
        webkit_available = False

    if args.backend is not None:
        return args.backend
    elif webkit_available:
        return 'webkit'
    else:
        return 'webengine'


def check_qt_version(backend):
    """Check if the Qt version is recent enough."""
    from PyQt5.QtCore import PYQT_VERSION, PYQT_VERSION_STR
    from qutebrowser.utils import qtutils, version
    if (not qtutils.version_check('5.2.0', strict=True) or
            PYQT_VERSION < 0x050200):
        text = ("Fatal error: Qt and PyQt >= 5.2.0 are required, but Qt {} / "
                "PyQt {} is installed.".format(version.qt_version(),
                                               PYQT_VERSION_STR))
        _die(text)
    elif (backend == 'webengine' and (
            not qtutils.version_check('5.7.1', strict=True) or
            PYQT_VERSION < 0x050700)):
        text = ("Fatal error: Qt >= 5.7.1 and PyQt >= 5.7 are required for "
                "QtWebEngine support, but Qt {} / PyQt {} is installed."
                .format(version.qt_version(), PYQT_VERSION_STR))
        _die(text)


def check_ssl_support(backend):
    """Check if SSL support is available."""
    from qutebrowser.utils import log

    try:
        from PyQt5.QtNetwork import QSslSocket
    except ImportError:
        _die("Fatal error: Your Qt is built without SSL support.")

    text = ("Could not initialize QtNetwork SSL support. If you use "
            "OpenSSL 1.1 with a PyQt package from PyPI (e.g. on Archlinux "
            "or Debian Stretch), you need to set LD_LIBRARY_PATH to the path "
            "of OpenSSL 1.0.")
    if backend == 'webengine':
        text += " This only affects downloads."

    if not QSslSocket.supportsSsl():
        if backend == 'webkit':
            _die("Could not initialize SSL support.")
        else:
            assert backend == 'webengine'
            log.init.warning(text)


def check_libraries(backend):
    """Check if all needed Python libraries are installed."""
    modules = {
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
    if backend == 'webengine':
        modules['PyQt5.QtWebEngineWidgets'] = _missing_str("QtWebEngine",
                                                           webengine=True)
        modules['PyQt5.QtOpenGL'] = _missing_str("PyQt5.QtOpenGL")
    else:
        assert backend == 'webkit'
        modules['PyQt5.QtWebKit'] = _missing_str("PyQt5.QtWebKit")
        modules['PyQt5.QtWebKitWidgets'] = _missing_str(
            "PyQt5.QtWebKitWidgets")

    from qutebrowser.utils import log

    for name, text in modules.items():
        try:
            # https://github.com/pallets/jinja/pull/628
            # https://bitbucket.org/birkenfeld/pygments-main/issues/1314/
            # https://github.com/pallets/jinja/issues/646
            # https://bitbucket.org/fdik/pypeg/commits/dd15ca462b532019c0a3be1d39b8ee2f3fa32f4e
            messages = ['invalid escape sequence',
                        'Flags not at the start of the expression']
            with log.ignore_py_warnings(
                    category=DeprecationWarning,
                    message=r'({})'.format('|'.join(messages))):
                importlib.import_module(name)
        except ImportError as e:
            _die(text, e)


def remove_inputhook():
    """Remove the PyQt input hook.

    Doing this means we can't use the interactive shell anymore (which we don't
    anyways), but we can use pdb instead.
    """
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


def check_optimize_flag():
    from qutebrowser.utils import log
    if sys.flags.optimize >= 2:
        log.init.warning("Running on optimize level higher than 1, "
                         "unexpected behavior may occur.")


def set_backend(backend):
    """Set the objects.backend global to the given backend (as string)."""
    from qutebrowser.misc import objects
    from qutebrowser.utils import usertypes
    backends = {
        'webkit': usertypes.Backend.QtWebKit,
        'webengine': usertypes.Backend.QtWebEngine,
    }
    objects.backend = backends[backend]


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
    # Init logging as early as possible
    init_log(args)
    # Now the faulthandler is enabled we fix the Qt harfbuzzing library, before
    # importing QtWidgets.
    fix_harfbuzz(args)
    # Now we can be sure QtCore is available, so we can print dialogs on
    # errors, so people only using the GUI notice them as well.
    backend = get_backend(args)
    check_qt_version(backend)
    remove_inputhook()
    check_libraries(backend)
    check_ssl_support(backend)
    check_optimize_flag()
    set_backend(backend)
