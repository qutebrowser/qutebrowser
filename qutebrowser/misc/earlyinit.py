# SPDX-FileCopyrightText: Florian Bruhin (The-Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Things which need to be done really early (e.g. before importing Qt).

At this point we can be sure we have all python 3.9 features available.
"""

try:
    # Importing hunter to register its atexit handler early so it gets called
    # late.
    import hunter  # pylint: disable=unused-import
except ImportError:
    hunter = None

import sys
import faulthandler
import traceback
import signal
import importlib
import datetime
from typing import NoReturn
try:
    import tkinter
except ImportError:
    tkinter = None  # type: ignore[assignment]

# NOTE: No qutebrowser or PyQt import should be done here, as some early
# initialization needs to take place before that!
#
# The machinery module is an exception, as it also is required to never import Qt
# itself at import time.
from qutebrowser.qt import machinery


START_TIME = datetime.datetime.now()


def _missing_str(name, *, webengine=False):
    """Get an error string for missing packages.

    Args:
        name: The name of the package.
        webengine: Whether this is checking the QtWebEngine package
    """
    blocks = ["Fatal error: <b>{}</b> is required to run qutebrowser but "
              "could not be imported! Maybe it's not installed?".format(name),
              "<b>The error encountered was:</b><br />%ERROR%"]
    lines = ['Please search for the python3 version of {} in your '
             'distributions packages, or see '
             'https://github.com/qutebrowser/qutebrowser/blob/main/doc/install.asciidoc'
             .format(name)]
    blocks.append('<br />'.join(lines))
    if not webengine:
        lines = ['<b>If you installed a qutebrowser package for your '
                 'distribution, please report this as a bug.</b>']
        blocks.append('<br />'.join(lines))
    return '<br /><br />'.join(blocks)


def _die(message, exception=None):
    """Display an error message using Qt and quit.

    We import the imports here as we want to do other stuff before the imports.

    Args:
        message: The message to display.
        exception: The exception object if we're handling an exception.
    """
    from qutebrowser.qt.widgets import QApplication, QMessageBox
    from qutebrowser.qt.core import Qt
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
        msgbox = QMessageBox(QMessageBox.Icon.Critical, "qutebrowser: Fatal error!",
                             message)
        msgbox.setTextFormat(Qt.TextFormat.RichText)
        msgbox.resize(msgbox.sizeHint())
        msgbox.exec()
    app.quit()
    sys.exit(1)


def init_faulthandler(fileobj=sys.__stderr__):
    """Enable faulthandler module if available.

    This print a nice traceback on segfaults.

    We use sys.__stderr__ instead of sys.stderr here so this will still work
    when sys.stderr got replaced, e.g. by "Python Tools for Visual Studio".

    Args:
        fileobj: An opened file object to write the traceback to.
    """
    try:
        faulthandler.enable(fileobj)
    except (RuntimeError, AttributeError):
        # When run with pythonw.exe, sys.__stderr__ can be None:
        # https://docs.python.org/3/library/sys.html#sys.__stderr__
        #
        # With PyInstaller, it can be a NullWriter raising AttributeError on
        # fileno: https://github.com/pyinstaller/pyinstaller/issues/4481
        #
        # Later when we have our data dir available we re-enable faulthandler
        # to write to a file so we can display a crash to the user at the next
        # start.
        #
        # Note that we don't have any logging initialized yet at this point, so
        # this is a silent error.
        return

    if (hasattr(faulthandler, 'register') and hasattr(signal, 'SIGUSR1') and
            sys.stderr is not None):
        # If available, we also want a traceback on SIGUSR1.
        # pylint: disable=no-member,useless-suppression
        faulthandler.register(signal.SIGUSR1)
        # pylint: enable=no-member,useless-suppression


def _fatal_qt_error(text: str) -> NoReturn:
    """Show a fatal error about Qt being missing."""
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


def check_qt_available(info: machinery.SelectionInfo) -> None:
    """Check if Qt core modules (QtCore/QtWidgets) are installed."""
    if info.wrapper is None:
        _fatal_qt_error(f"No Qt wrapper was importable.\n\n{info}")

    packages = [f'{info.wrapper}.QtCore', f'{info.wrapper}.QtWidgets']
    for name in packages:
        try:
            importlib.import_module(name)
        except ImportError as e:
            text = _missing_str(name)
            text = text.replace('<b>', '')
            text = text.replace('</b>', '')
            text = text.replace('<br />', '\n')
            text = text.replace('%ERROR%', str(e))
            text += '\n\n' + str(info)
            _fatal_qt_error(text)


def qt_version(qversion=None, qt_version_str=None):
    """Get a Qt version string based on the runtime/compiled versions."""
    if qversion is None:
        from qutebrowser.qt.core import qVersion
        qversion = qVersion()
    if qt_version_str is None:
        from qutebrowser.qt.core import QT_VERSION_STR
        qt_version_str = QT_VERSION_STR

    if qversion != qt_version_str:
        return '{} (compiled {})'.format(qversion, qt_version_str)
    else:
        return qversion


def get_qt_version():
    """Get the Qt version, or None if too old for QLibraryInfo.version()."""
    try:
        from qutebrowser.qt.core import QLibraryInfo
        return QLibraryInfo.version().normalized()
    except (ImportError, AttributeError):
        return None


def check_qt_version():
    """Check if the Qt version is recent enough."""
    from qutebrowser.qt.core import QT_VERSION, PYQT_VERSION, PYQT_VERSION_STR
    from qutebrowser.qt.core import QVersionNumber
    qt_ver = get_qt_version()
    recent_qt_runtime = qt_ver is not None and qt_ver >= QVersionNumber(5, 15)

    if QT_VERSION < 0x050F00 or PYQT_VERSION < 0x050F00 or not recent_qt_runtime:
        text = ("Fatal error: Qt >= 5.15.0 and PyQt >= 5.15.0 are required, "
                "but Qt {} / PyQt {} is installed.".format(qt_version(),
                                                           PYQT_VERSION_STR))
        _die(text)

    if 0x060000 <= PYQT_VERSION < 0x060202:
        text = ("Fatal error: With Qt 6, PyQt >= 6.2.2 is required, but "
                "{} is installed.".format(PYQT_VERSION_STR))
        _die(text)


def check_ssl_support():
    """Check if SSL support is available."""
    try:
        from qutebrowser.qt.network import QSslSocket  # pylint: disable=unused-import
    except ImportError:
        _die("Fatal error: Your Qt is built without SSL support.")


def _check_modules(modules):
    """Make sure the given modules are available."""
    from qutebrowser.utils import log

    for name, text in modules.items():
        try:
            with log.py_warning_filter(
                category=DeprecationWarning,
                message=r'invalid escape sequence'
            ), log.py_warning_filter(
                category=ImportWarning,
                message=r'Not importing directory .*: missing __init__'
            ), log.py_warning_filter(
                category=DeprecationWarning,
                message=r'the imp module is deprecated',
            ), log.py_warning_filter(
                # WORKAROUND for https://github.com/pypa/setuptools/issues/2466
                category=DeprecationWarning,
                message=r'Creating a LegacyVersion has been deprecated',
            ):
                importlib.import_module(name)
        except ImportError as e:
            _die(text, e)


def check_libraries():
    """Check if all needed Python libraries are installed."""
    modules = {
        'jinja2': _missing_str("jinja2"),
        'yaml': _missing_str("PyYAML"),
    }

    for subpkg in ['QtQml', 'QtOpenGL', 'QtDBus']:
        package = f'{machinery.INFO.wrapper}.{subpkg}'
        modules[package] = _missing_str(package)

    if sys.platform.startswith('darwin'):
        from qutebrowser.qt.core import QVersionNumber
        qt_ver = get_qt_version()
        if qt_ver is not None and qt_ver < QVersionNumber(6, 3):
            # Used for resizable hide_decoration windows on macOS
            modules['objc'] = _missing_str("pyobjc-core")
            modules['AppKit'] = _missing_str("pyobjc-framework-Cocoa")

    _check_modules(modules)


def configure_pyqt():
    """Remove the PyQt input hook and enable overflow checking.

    Doing this means we can't use the interactive shell anymore (which we don't
    anyways), but we can use pdb instead.
    """
    from qutebrowser.qt.core import pyqtRemoveInputHook
    pyqtRemoveInputHook()

    from qutebrowser.qt import sip
    if machinery.IS_QT5:
        # default in PyQt6
        sip.enableoverflowchecking(True)


def init_log(args):
    """Initialize logging.

    Args:
        args: The argparse namespace.
    """
    from qutebrowser.utils import log
    log.init_log(args)
    log.init.debug("Log initialized.")


def init_qtlog(args):
    """Initialize Qt logging.

    Args:
        args: The argparse namespace.
    """
    from qutebrowser.utils import log, qtlog
    qtlog.init(args)
    log.init.debug("Qt log initialized.")


def check_optimize_flag():
    """Check whether qutebrowser is running with -OO."""
    from qutebrowser.utils import log
    if sys.flags.optimize >= 2:
        log.init.warning("Running on optimize level higher than 1, "
                         "unexpected behavior may occur.")


def webengine_early_import():
    """If QtWebEngine is available, import it early.

    We need to ensure that QtWebEngine is imported before a QApplication is created for
    everything to work properly.

    This needs to be done even when using the QtWebKit backend, to ensure that e.g.
    error messages in backendproblem.py are accurate.
    """
    try:
        from qutebrowser.qt import webenginewidgets  # pylint: disable=unused-import
    except ImportError:
        pass


def early_init(args):
    """Do all needed early initialization.

    Note that it's vital the other earlyinit functions get called in the right
    order!

    Args:
        args: The argparse namespace.
    """
    # Init logging as early as possible
    init_log(args)
    # First we initialize the faulthandler as early as possible, so we
    # theoretically could catch segfaults occurring later during earlyinit.
    init_faulthandler()
    # Then we configure the selected Qt wrapper
    info = machinery.init(args)
    # Here we check if QtCore is available, and if not, print a message to the
    # console or via Tk.
    check_qt_available(info)
    # Init Qt logging after machinery is initialized
    init_qtlog(args)
    # Now we can be sure QtCore is available, so we can print dialogs on
    # errors, so people only using the GUI notice them as well.
    check_libraries()
    check_qt_version()
    configure_pyqt()
    check_ssl_support()
    check_optimize_flag()
    webengine_early_import()
