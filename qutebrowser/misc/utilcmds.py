# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Misc. utility commands exposed to the user."""

# QApplication and objects are imported so they're usable in :debug-pyeval

import functools
import os
import traceback
import typing

from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QApplication

from qutebrowser.browser import qutescheme
from qutebrowser.utils import log, objreg, usertypes, message, debug, utils
from qutebrowser.keyinput import modeman
from qutebrowser.commands import runners
from qutebrowser.api import cmdutils
from qutebrowser.misc import (  # pylint: disable=unused-import
    consolewidget, debugcachestats, objects, miscwidgets)
from qutebrowser.utils.version import pastebin_version
from qutebrowser.qt import sip


@cmdutils.register(maxsplit=1, no_cmd_split=True, no_replace_variables=True)
@cmdutils.argument('win_id', value=cmdutils.Value.win_id)
def later(ms: int, command: str, win_id: int) -> None:
    """Execute a command after some time.

    Args:
        ms: How many milliseconds to wait.
        command: The command to run, with optional args.
    """
    if ms < 0:
        raise cmdutils.CommandError("I can't run something in the past!")
    commandrunner = runners.CommandRunner(win_id)
    timer = usertypes.Timer(name='later', parent=QApplication.instance())
    try:
        timer.setSingleShot(True)
        try:
            timer.setInterval(ms)
        except OverflowError:
            raise cmdutils.CommandError("Numeric argument is too large for "
                                        "internal int representation.")
        timer.timeout.connect(
            functools.partial(commandrunner.run_safely, command))
        timer.timeout.connect(timer.deleteLater)
        timer.start()
    except:
        timer.deleteLater()
        raise


@cmdutils.register(maxsplit=1, no_cmd_split=True, no_replace_variables=True)
@cmdutils.argument('win_id', value=cmdutils.Value.win_id)
@cmdutils.argument('count', value=cmdutils.Value.count)
def repeat(times: int, command: str, win_id: int, count: int = None) -> None:
    """Repeat a given command.

    Args:
        times: How many times to repeat.
        command: The command to run, with optional args.
        count: Multiplies with 'times' when given.
    """
    if count is not None:
        times *= count

    if times < 0:
        raise cmdutils.CommandError("A negative count doesn't make sense.")
    commandrunner = runners.CommandRunner(win_id)
    for _ in range(times):
        commandrunner.run_safely(command)


@cmdutils.register(maxsplit=1, no_cmd_split=True, no_replace_variables=True)
@cmdutils.argument('win_id', value=cmdutils.Value.win_id)
@cmdutils.argument('count', value=cmdutils.Value.count)
def run_with_count(count_arg: int, command: str, win_id: int,
                   count: int = 1) -> None:
    """Run a command with the given count.

    If run_with_count itself is run with a count, it multiplies count_arg.

    Args:
        count_arg: The count to pass to the command.
        command: The command to run, with optional args.
        count: The count that run_with_count itself received.
    """
    runners.CommandRunner(win_id).run(command, count_arg * count)


@cmdutils.register()
def clear_messages() -> None:
    """Clear all message notifications."""
    message.global_bridge.clear_messages.emit()


@cmdutils.register(debug=True)
def debug_all_objects() -> None:
    """Print a list of  all objects to the debug log."""
    s = debug.get_all_objects()
    log.misc.debug(s)


@cmdutils.register(debug=True)
def debug_cache_stats() -> None:
    """Print LRU cache stats."""
    debugcachestats.debug_cache_stats()


@cmdutils.register(debug=True)
def debug_console() -> None:
    """Show the debugging console."""
    if consolewidget.console_widget is None:
        log.misc.debug('initializing debug console')
        consolewidget.init()

    assert consolewidget.console_widget is not None

    if consolewidget.console_widget.isVisible():
        log.misc.debug('hiding debug console')
        consolewidget.console_widget.hide()
    else:
        log.misc.debug('showing debug console')
        consolewidget.console_widget.show()


@cmdutils.register(maxsplit=0, debug=True, no_cmd_split=True)
def debug_pyeval(s: str, file: bool = False, quiet: bool = False) -> None:
    """Evaluate a python string and display the results as a web page.

    Args:
        s: The string to evaluate.
        file: Interpret s as a path to file, also implies --quiet.
        quiet: Don't show the output in a new tab.
    """
    if file:
        quiet = True
        path = os.path.expanduser(s)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                s = f.read()
        except OSError as e:
            raise cmdutils.CommandError(str(e))
        try:
            exec(s)
            out = "No error"
        except Exception:
            out = traceback.format_exc()
    else:
        try:
            r = eval(s)
            out = repr(r)
        except Exception:
            out = traceback.format_exc()

    qutescheme.pyeval_output = out
    if quiet:
        log.misc.debug("pyeval output: {}".format(out))
    else:
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window='last-focused')
        tabbed_browser.load_url(QUrl('qute://pyeval'), newtab=True)


@cmdutils.register(debug=True)
def debug_set_fake_clipboard(s: str = None) -> None:
    """Put data into the fake clipboard and enable logging, used for tests.

    Args:
        s: The text to put into the fake clipboard, or unset to enable logging.
    """
    if s is None:
        utils.log_clipboard = True
    else:
        utils.fake_clipboard = s


@cmdutils.register()
@cmdutils.argument('win_id', value=cmdutils.Value.win_id)
@cmdutils.argument('count', value=cmdutils.Value.count)
def repeat_command(win_id: int, count: int = None) -> None:
    """Repeat the last executed command.

    Args:
        count: Which count to pass the command.
    """
    mode_manager = modeman.instance(win_id)
    if mode_manager.mode not in runners.last_command:
        raise cmdutils.CommandError("You didn't do anything yet.")
    cmd = runners.last_command[mode_manager.mode]
    commandrunner = runners.CommandRunner(win_id)
    commandrunner.run(cmd[0], count if count is not None else cmd[1])


@cmdutils.register(debug=True, name='debug-log-capacity')
def log_capacity(capacity: int) -> None:
    """Change the number of log lines to be stored in RAM.

    Args:
       capacity: Number of lines for the log.
    """
    if capacity < 0:
        raise cmdutils.CommandError("Can't set a negative log capacity!")
    assert log.ram_handler is not None
    log.ram_handler.change_log_capacity(capacity)


@cmdutils.register(debug=True)
@cmdutils.argument('level', choices=sorted(
    (level.lower() for level in log.LOG_LEVELS),
    key=lambda e: log.LOG_LEVELS[e.upper()]))
def debug_log_level(level: str) -> None:
    """Change the log level for console logging.

    Args:
        level: The log level to set.
    """
    if log.console_handler is None:
        raise cmdutils.CommandError("No log.console_handler. Not attached "
                                    "to a console?")

    log.change_console_formatter(log.LOG_LEVELS[level.upper()])
    log.console_handler.setLevel(log.LOG_LEVELS[level.upper()])


@cmdutils.register(debug=True)
def debug_log_filter(filters: str) -> None:
    """Change the log filter for console logging.

    Args:
        filters: A comma separated list of logger names. Can also be "none" to
                 clear any existing filters.
    """
    if log.console_filter is None:
        raise cmdutils.CommandError("No log.console_filter. Not attached "
                                    "to a console?")

    if filters.strip().lower() == 'none':
        log.console_filter.names = None
        return

    if not set(filters.split(',')).issubset(log.LOGGER_NAMES):
        raise cmdutils.CommandError("filters: Invalid value {} - expected one "
                                    "of: {}".format(
                                        filters, ', '.join(log.LOGGER_NAMES)))

    log.console_filter.names = filters.split(',')


@cmdutils.register()
@cmdutils.argument('current_win_id', value=cmdutils.Value.win_id)
def window_only(current_win_id: int) -> None:
    """Close all windows except for the current one."""
    for win_id, window in objreg.window_registry.items():

        # We could be in the middle of destroying a window here
        if sip.isdeleted(window):
            continue

        if win_id != current_win_id:
            window.close()


@cmdutils.register()
@cmdutils.argument('win_id', value=cmdutils.Value.win_id)
def version(win_id: int, paste: bool = False) -> None:
    """Show version information.

    Args:
        paste: Paste to pastebin.
    """
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)
    tabbed_browser.load_url(QUrl('qute://version/'), newtab=True)

    if paste:
        pastebin_version()


_keytester_widget = None  # type: typing.Optional[miscwidgets.KeyTesterWidget]


@cmdutils.register(debug=True)
def debug_keytester() -> None:
    """Show a keytester widget."""
    global _keytester_widget
    if _keytester_widget and _keytester_widget.isVisible():
        _keytester_widget.close()
    else:
        _keytester_widget = miscwidgets.KeyTesterWidget()
        _keytester_widget.show()
