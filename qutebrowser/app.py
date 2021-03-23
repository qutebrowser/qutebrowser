# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Initialization of qutebrowser and application-wide things.

The run() function will get called once early initialization (in
qutebrowser.py/earlyinit.py) is done. See the qutebrowser.py docstring for
details about early initialization.

As we need to access the config before the QApplication is created, we
initialize everything the config needs before the QApplication is created, and
then leave it in a partially initialized state (no saving, no config errors
shown yet).

We then set up the QApplication object and initialize a few more low-level
things.

After that, init() and _init_modules() take over and initialize the rest.

After all initialization is done, the qt_mainloop() function is called, which
blocks and spins the Qt mainloop.
"""

import os
import sys
import functools
import tempfile
import datetime
import argparse
from typing import Iterable, Optional, cast

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtGui import QDesktopServices, QPixmap, QIcon
from PyQt5.QtCore import pyqtSlot, QUrl, QObject, QEvent, pyqtSignal, Qt

import qutebrowser
import qutebrowser.resources
from qutebrowser.commands import runners
from qutebrowser.config import (config, websettings, configfiles, configinit,
                                qtargs)
from qutebrowser.browser import (urlmarks, history, browsertab,
                                 qtnetworkdownloads, downloads, greasemonkey)
from qutebrowser.browser.network import proxy
from qutebrowser.browser.webkit import cookies, cache
from qutebrowser.browser.webkit.network import networkmanager
from qutebrowser.extensions import loader
from qutebrowser.keyinput import macros, eventfilter
from qutebrowser.mainwindow import mainwindow, prompt, windowundo
from qutebrowser.misc import (ipc, savemanager, sessions, crashsignal,
                              earlyinit, sql, cmdhistory, backendproblem,
                              objects, quitter)
from qutebrowser.utils import (log, version, message, utils, urlutils, objreg,
                               resources, usertypes, standarddir,
                               error, qtutils, debug)
# pylint: disable=unused-import
# We import those to run the cmdutils.register decorators.
from qutebrowser.mainwindow.statusbar import command
from qutebrowser.misc import utilcmds
from qutebrowser.browser import commands
# pylint: enable=unused-import


q_app = cast(QApplication, None)


def run(args):
    """Initialize everything and run the application."""
    if args.temp_basedir:
        args.basedir = tempfile.mkdtemp(prefix='qutebrowser-basedir-')

    log.init.debug("Main process PID: {}".format(os.getpid()))

    log.init.debug("Initializing directories...")
    standarddir.init(args)
    resources.preload()

    log.init.debug("Initializing config...")
    configinit.early_init(args)

    log.init.debug("Initializing application...")
    app = Application(args)
    objects.qapp = app
    app.setOrganizationName("qutebrowser")
    app.setApplicationName("qutebrowser")
    # Default DesktopFileName is org.qutebrowser.qutebrowser, set in `get_argparser()`
    app.setDesktopFileName(args.desktop_file_name)
    app.setApplicationVersion(qutebrowser.__version__)

    if args.version:
        print(version.version_info())
        sys.exit(usertypes.Exit.ok)

    quitter.init(args)
    crashsignal.init(q_app=app, args=args, quitter=quitter.instance)

    try:
        server = ipc.send_or_listen(args)
    except ipc.Error:
        # ipc.send_or_listen already displays the error message for us.
        # We didn't really initialize much so far, so we just quit hard.
        sys.exit(usertypes.Exit.err_ipc)

    if server is None:
        if args.backend is not None:
            log.init.warning(
                "Backend from the running instance will be used")
        sys.exit(usertypes.Exit.ok)

    init(args=args)

    quitter.instance.shutting_down.connect(server.shutdown)
    server.got_args.connect(
        lambda args, target_arg, cwd:
        process_pos_args(args, cwd=cwd, via_ipc=True, target_arg=target_arg))

    ret = qt_mainloop()
    return ret


def qt_mainloop():
    """Simple wrapper to get a nicer stack trace for segfaults.

    WARNING: misc/crashdialog.py checks the stacktrace for this function
    name, so if this is changed, it should be changed there as well!
    """
    return objects.qapp.exec()


def init(*, args: argparse.Namespace) -> None:
    """Initialize everything."""
    log.init.debug("Starting init...")

    crashsignal.crash_handler.init_faulthandler()

    objects.qapp.setQuitOnLastWindowClosed(False)
    quitter.instance.shutting_down.connect(QApplication.closeAllWindows)

    _init_icon()
    _init_pulseaudio()

    loader.init()
    loader.load_components()
    try:
        _init_modules(args=args)
    except (OSError, UnicodeDecodeError, browsertab.WebTabError) as e:
        error.handle_fatal_exc(e, "Error while initializing!",
                               no_err_windows=args.no_err_windows,
                               pre_text="Error while initializing")
        sys.exit(usertypes.Exit.err_init)

    log.init.debug("Initializing eventfilter...")
    eventfilter.init()

    log.init.debug("Connecting signals...")
    objects.qapp.focusChanged.connect(on_focus_changed)

    _process_args(args)

    for scheme in ['http', 'https', 'qute']:
        QDesktopServices.setUrlHandler(
            scheme, open_desktopservices_url)

    log.init.debug("Init done!")
    crashsignal.crash_handler.raise_crashdlg()


def _init_icon():
    """Initialize the icon of qutebrowser."""
    fallback_icon = QIcon()
    for size in [16, 24, 32, 48, 64, 96, 128, 256, 512]:
        filename = ':/icons/qutebrowser-{size}x{size}.png'.format(size=size)
        pixmap = QPixmap(filename)
        if pixmap.isNull():
            log.init.warning("Failed to load {}".format(filename))
        else:
            fallback_icon.addPixmap(pixmap)
    icon = QIcon.fromTheme('qutebrowser', fallback_icon)
    if icon.isNull():
        log.init.warning("Failed to load icon")
    else:
        objects.qapp.setWindowIcon(icon)


def _init_pulseaudio():
    """Set properties for PulseAudio.

    WORKAROUND for https://bugreports.qt.io/browse/QTBUG-85363

    Affected Qt versions:
    - Older than 5.11 (which is unsupported)
    - 5.14.0 to 5.15.0 (inclusive)

    However, we set this on all versions so that qutebrowser's icon gets picked
    up as well.
    """
    for prop in ['application.name', 'application.icon_name']:
        os.environ['PULSE_PROP_OVERRIDE_' + prop] = 'qutebrowser'


def _process_args(args):
    """Open startpage etc. and process commandline args."""
    if not args.override_restore:
        sessions.load_default(args.session)

    if not sessions.session_manager.did_load:
        log.init.debug("Initializing main window...")
        private = args.target == 'private-window'
        if (config.val.content.private_browsing or
                private) and qtutils.is_single_process():
            err = Exception("Private windows are unavailable with "
                            "the single-process process model.")
            error.handle_fatal_exc(err, 'Cannot start in private mode',
                                   no_err_windows=args.no_err_windows)
            sys.exit(usertypes.Exit.err_init)
        window = mainwindow.MainWindow(private=private)
        if not args.nowindow:
            window.show()
        objects.qapp.setActiveWindow(window)

    process_pos_args(args.command)
    _open_startpage()
    _open_special_pages(args)

    delta = datetime.datetime.now() - earlyinit.START_TIME
    log.init.debug("Init finished after {}s".format(delta.total_seconds()))


def process_pos_args(args, via_ipc=False, cwd=None, target_arg=None):
    """Process positional commandline args.

    URLs to open have no prefix, commands to execute begin with a colon.

    Args:
        args: A list of arguments to process.
        via_ipc: Whether the arguments were transmitted over IPC.
        cwd: The cwd to use for fuzzy_url.
        target_arg: Command line argument received by a running instance via
                    ipc. If the --target argument was not specified, target_arg
                    will be an empty string.
    """
    new_window_target = ('private-window' if target_arg == 'private-window'
                         else 'window')
    command_target = config.val.new_instance_open_target
    if command_target in {'window', 'private-window'}:
        command_target = 'tab-silent'

    win_id: Optional[int] = None

    if via_ipc and (not args or args == ['']):
        win_id = mainwindow.get_window(via_ipc=via_ipc,
                                       target=new_window_target)
        _open_startpage(win_id)
        return

    for cmd in args:
        if cmd.startswith(':'):
            if win_id is None:
                win_id = mainwindow.get_window(via_ipc=via_ipc,
                                               target=command_target)
            log.init.debug("Startup cmd {!r}".format(cmd))
            commandrunner = runners.CommandRunner(win_id)
            commandrunner.run_safely(cmd[1:])
        elif not cmd:
            log.init.debug("Empty argument")
            win_id = mainwindow.get_window(via_ipc=via_ipc,
                                           target=new_window_target)
        else:
            if via_ipc and target_arg and target_arg != 'auto':
                open_target = target_arg
            else:
                open_target = None
            if not cwd:  # could also be an empty string due to the PyQt signal
                cwd = None
            try:
                url = urlutils.fuzzy_url(cmd, cwd, relative=True)
            except urlutils.InvalidUrlError as e:
                message.error("Error in startup argument '{}': {}".format(
                    cmd, e))
            else:
                win_id = open_url(url, target=open_target, via_ipc=via_ipc)


def open_url(url, target=None, no_raise=False, via_ipc=True):
    """Open a URL in new window/tab.

    Args:
        url: A URL to open.
        target: same as new_instance_open_target (used as a default).
        no_raise: suppress target window raising.
        via_ipc: Whether the arguments were transmitted over IPC.

    Return:
        ID of a window that was used to open URL
    """
    target = target or config.val.new_instance_open_target
    background = target in {'tab-bg', 'tab-bg-silent'}
    win_id = mainwindow.get_window(via_ipc=via_ipc, target=target,
                                   no_raise=no_raise)
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)
    log.init.debug("About to open URL: {}".format(url.toDisplayString()))
    tabbed_browser.tabopen(url, background=background, related=False)
    return win_id


def _open_startpage(win_id=None):
    """Open startpage.

    The startpage is never opened if the given windows are not empty.

    Args:
        win_id: If None, open startpage in all empty windows.
                If set, open the startpage in the given window.
    """
    if win_id is not None:
        window_ids: Iterable[int] = [win_id]
    else:
        window_ids = objreg.window_registry
    for cur_win_id in list(window_ids):  # Copying as the dict could change
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=cur_win_id)
        if tabbed_browser.widget.count() == 0:
            log.init.debug("Opening start pages")
            for url in config.val.url.start_pages:
                tabbed_browser.tabopen(url)


def _open_special_pages(args):
    """Open special notification pages which are only shown once.

    Args:
        args: The argparse namespace.
    """
    if args.basedir is not None:
        # With --basedir given, don't open anything.
        return

    general_sect = configfiles.state['general']
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window='last-focused')

    pages = [
        # state, condition, URL
        ('quickstart-done',
         True,
         'https://www.qutebrowser.org/quickstart.html'),

        ('config-migration-shown',
         os.path.exists(os.path.join(standarddir.config(),
                                     'qutebrowser.conf')),
         'qute://help/configuring.html'),

        ('webkit-warning-shown',
         objects.backend == usertypes.Backend.QtWebKit,
         'qute://warning/webkit'),

        ('session-warning-shown',
         qtutils.version_check('5.15', compiled=False),
         'qute://warning/sessions'),
    ]

    if 'quickstart-done' not in general_sect:
        # New users aren't going to be affected by the Qt 5.15 session change much, as
        # they aren't used to qutebrowser saving the full back/forward history in
        # sessions.
        general_sect['session-warning-shown'] = '1'

    for state, condition, url in pages:
        if general_sect.get(state) != '1' and condition:
            tabbed_browser.tabopen(QUrl(url), background=False)
            general_sect[state] = '1'

    # Show changelog on new releases
    change = configfiles.state.qutebrowser_version_changed
    if change == configfiles.VersionChange.equal:
        return

    setting = config.val.changelog_after_upgrade
    if not change.matches_filter(setting):
        log.init.debug(
            f"Showing changelog is disabled (setting {setting}, change {change})")
        return

    try:
        changelog = resources.read_file('html/doc/changelog.html')
    except OSError as e:
        log.init.warning(f"Not showing changelog due to {e}")
        return

    qbversion = qutebrowser.__version__
    if f'id="v{qbversion}"' not in changelog:
        log.init.warning("Not showing changelog (anchor not found)")
        return

    message.info(f"Showing changelog after upgrade to qutebrowser v{qbversion}.")
    changelog_url = f'qute://help/changelog.html#v{qbversion}'
    tabbed_browser.tabopen(QUrl(changelog_url), background=False)


def on_focus_changed(_old, new):
    """Register currently focused main window in the object registry."""
    if new is None:
        return

    if not isinstance(new, QWidget):
        log.misc.debug("on_focus_changed called with non-QWidget {!r}".format(
            new))
        return

    window = new.window()
    if isinstance(window, mainwindow.MainWindow):
        objreg.register('last-focused-main-window', window, update=True)
        # A focused window must also be visible, and in this case we should
        # consider it as the most recently looked-at window
        objreg.register('last-visible-main-window', window, update=True)


def open_desktopservices_url(url):
    """Handler to open a URL via QDesktopServices."""
    target = config.val.new_instance_open_target
    win_id = mainwindow.get_window(via_ipc=True, target=target)
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)
    tabbed_browser.tabopen(url)


# This is effectively a @config.change_filter
# However, logging is initialized too early to use that annotation
def _on_config_changed(name: str) -> None:
    if name.startswith('logging.'):
        log.init_from_config(config.val)


def _init_modules(*, args):
    """Initialize all 'modules' which need to be initialized.

    Args:
        args: The argparse namespace.
    """
    log.init.debug("Initializing logging from config...")
    log.init_from_config(config.val)
    config.instance.changed.connect(_on_config_changed)

    log.init.debug("Initializing save manager...")
    save_manager = savemanager.SaveManager(objects.qapp)
    objreg.register('save-manager', save_manager)
    quitter.instance.shutting_down.connect(save_manager.shutdown)
    configinit.late_init(save_manager)

    log.init.debug("Checking backend requirements...")
    backendproblem.init(args=args, save_manager=save_manager)

    log.init.debug("Initializing prompts...")
    prompt.init()

    log.init.debug("Initializing network...")
    networkmanager.init()

    log.init.debug("Initializing proxy...")
    proxy.init()
    quitter.instance.shutting_down.connect(proxy.shutdown)

    log.init.debug("Initializing downloads...")
    downloads.init()
    quitter.instance.shutting_down.connect(downloads.shutdown)

    with debug.log_time("init", "Initializing SQL/history"):
        try:
            log.init.debug("Initializing SQL...")
            sql.init(os.path.join(standarddir.data(), 'history.sqlite'))

            log.init.debug("Initializing web history...")
            history.init(objects.qapp)
        except sql.KnownError as e:
            error.handle_fatal_exc(e, 'Error initializing SQL',
                                   pre_text='Error initializing SQL',
                                   no_err_windows=args.no_err_windows)
            sys.exit(usertypes.Exit.err_init)

    log.init.debug("Initializing command history...")
    cmdhistory.init()

    log.init.debug("Initializing websettings...")
    websettings.init(args)
    quitter.instance.shutting_down.connect(websettings.shutdown)

    log.init.debug("Initializing sessions...")
    sessions.init(objects.qapp)

    if not args.no_err_windows:
        crashsignal.crash_handler.display_faulthandler()

    log.init.debug("Initializing quickmarks...")
    quickmark_manager = urlmarks.QuickmarkManager(objects.qapp)
    objreg.register('quickmark-manager', quickmark_manager)

    log.init.debug("Initializing bookmarks...")
    bookmark_manager = urlmarks.BookmarkManager(objects.qapp)
    objreg.register('bookmark-manager', bookmark_manager)

    log.init.debug("Initializing cookies...")
    cookies.init(objects.qapp)

    log.init.debug("Initializing cache...")
    cache.init(objects.qapp)

    log.init.debug("Initializing downloads...")
    qtnetworkdownloads.init()

    log.init.debug("Initializing Greasemonkey...")
    greasemonkey.init()

    log.init.debug("Misc initialization...")
    macros.init()
    windowundo.init()


class Application(QApplication):

    """Main application instance.

    Attributes:
        _args: ArgumentParser instance.
        _last_focus_object: The last focused object's repr.

    Signals:
        new_window: A new window was created.
        window_closing: A window is being closed.
    """

    new_window = pyqtSignal(mainwindow.MainWindow)
    window_closing = pyqtSignal(mainwindow.MainWindow)

    def __init__(self, args):
        """Constructor.

        Args:
            Argument namespace from argparse.
        """
        self._last_focus_object = None

        qt_args = qtargs.qt_args(args)
        log.init.debug("Commandline args: {}".format(sys.argv[1:]))
        log.init.debug("Parsed: {}".format(args))
        log.init.debug("Qt arguments: {}".format(qt_args[1:]))
        super().__init__(qt_args)

        objects.args = args

        log.init.debug("Initializing application...")

        self.launch_time = datetime.datetime.now()
        self.focusObjectChanged.connect(  # type: ignore[attr-defined]
            self.on_focus_object_changed)
        self.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

        self.new_window.connect(self._on_new_window)

    @pyqtSlot(mainwindow.MainWindow)
    def _on_new_window(self, window):
        window.tabbed_browser.shutting_down.connect(functools.partial(
            self.window_closing.emit, window))

    @pyqtSlot(QObject)
    def on_focus_object_changed(self, obj):
        """Log when the focus object changed."""
        output = repr(obj)
        if self._last_focus_object != output:
            log.misc.debug("Focus object changed: {}".format(output))
        self._last_focus_object = output

    def event(self, e):
        """Handle macOS FileOpen events."""
        if e.type() != QEvent.FileOpen:
            return super().event(e)

        url = e.url()
        if url.isValid():
            open_url(url, no_raise=True)
        else:
            message.error("Invalid URL: {}".format(url.errorString()))

        return True

    def __repr__(self):
        return utils.get_repr(self)
