# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import functools
import types
import traceback

try:
    import hunter
except ImportError:
    hunter = None

from qutebrowser.browser.webkit.network import qutescheme
from qutebrowser.utils import log, objreg, usertypes, message, debug, utils
from qutebrowser.commands import cmdutils, runners, cmdexc
from qutebrowser.config import style
from qutebrowser.misc import consolewidget

from PyQt5.QtCore import QUrl
# so it's available for :debug-pyeval
from PyQt5.QtWidgets import QApplication  # pylint: disable=unused-import


@cmdutils.register(maxsplit=1, no_cmd_split=True)
@cmdutils.argument('win_id', win_id=True)
def later(ms: int, command, win_id):
    """Execute a command after some time.

    Args:
        ms: How many milliseconds to wait.
        command: The command to run, with optional args.
    """
    if ms < 0:
        raise cmdexc.CommandError("I can't run something in the past!")
    commandrunner = runners.CommandRunner(win_id)
    app = objreg.get('app')
    timer = usertypes.Timer(name='later', parent=app)
    try:
        timer.setSingleShot(True)
        try:
            timer.setInterval(ms)
        except OverflowError:
            raise cmdexc.CommandError("Numeric argument is too large for "
                                      "internal int representation.")
        timer.timeout.connect(
            functools.partial(commandrunner.run_safely, command))
        timer.timeout.connect(timer.deleteLater)
        timer.start()
    except:
        timer.deleteLater()
        raise


@cmdutils.register(maxsplit=1, no_cmd_split=True)
@cmdutils.argument('win_id', win_id=True)
def repeat(times: int, command, win_id):
    """Repeat a given command.

    Args:
        times: How many times to repeat.
        command: The command to run, with optional args.
    """
    if times < 0:
        raise cmdexc.CommandError("A negative count doesn't make sense.")
    commandrunner = runners.CommandRunner(win_id)
    for _ in range(times):
        commandrunner.run_safely(command)


@cmdutils.register(hide=True)
@cmdutils.argument('win_id', win_id=True)
def message_error(win_id, text):
    """Show an error message in the statusbar.

    Args:
        text: The text to show.
    """
    message.error(win_id, text)


@cmdutils.register(hide=True)
@cmdutils.argument('win_id', win_id=True)
def message_info(win_id, text):
    """Show an info message in the statusbar.

    Args:
        text: The text to show.
    """
    message.info(win_id, text)


@cmdutils.register(hide=True)
@cmdutils.argument('win_id', win_id=True)
def message_warning(win_id, text):
    """Show a warning message in the statusbar.

    Args:
        text: The text to show.
    """
    message.warning(win_id, text)


@cmdutils.register(debug=True)
@cmdutils.argument('typ', choices=['exception', 'segfault'])
def debug_crash(typ='exception'):
    """Crash for debugging purposes.

    Args:
        typ: either 'exception' or 'segfault'.
    """
    if typ == 'segfault':
        # From python's Lib/test/crashers/bogus_code_obj.py
        co = types.CodeType(0, 0, 0, 0, 0, b'\x04\x71\x00\x00', (), (), (),
                            '', '', 1, b'')
        exec(co)
        raise Exception("Segfault failed (wat.)")
    else:
        raise Exception("Forced crash")


@cmdutils.register(debug=True)
def debug_all_objects():
    """Print a list of  all objects to the debug log."""
    s = debug.get_all_objects()
    log.misc.debug(s)


@cmdutils.register(debug=True)
def debug_cache_stats():
    """Print LRU cache stats."""
    config_info = objreg.get('config').get.cache_info()
    style_info = style.get_stylesheet.cache_info()
    log.misc.debug('config: {}'.format(config_info))
    log.misc.debug('style: {}'.format(style_info))


@cmdutils.register(debug=True)
def debug_console():
    """Show the debugging console."""
    try:
        con_widget = objreg.get('debug-console')
    except KeyError:
        con_widget = consolewidget.ConsoleWidget()
        objreg.register('debug-console', con_widget)

    if con_widget.isVisible():
        con_widget.hide()
    else:
        con_widget.show()


@cmdutils.register(debug=True, maxsplit=0, no_cmd_split=True)
def debug_trace(expr=""):
    """Trace executed code via hunter.

    Args:
        expr: What to trace, passed to hunter.
    """
    if hunter is None:
        raise cmdexc.CommandError("You need to install 'hunter' to use this "
                                  "command!")
    try:
        eval('hunter.trace({})'.format(expr))
    except Exception as e:
        raise cmdexc.CommandError("{}: {}".format(e.__class__.__name__, e))


@cmdutils.register(maxsplit=0, debug=True, no_cmd_split=True)
def debug_pyeval(s, quiet=False):
    """Evaluate a python string and display the results as a web page.

    Args:
        s: The string to evaluate.
        quiet: Don't show the output in a new tab.
    """
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
        tabbed_browser.openurl(QUrl('qute:pyeval'), newtab=True)


@cmdutils.register(debug=True)
def debug_set_fake_clipboard(s=None):
    """Put data into the fake clipboard and enable logging, used for tests.

    Args:
        s: The text to put into the fake clipboard, or unset to enable logging.
    """
    if s is None:
        utils.log_clipboard = True
    else:
        utils.fake_clipboard = s


@cmdutils.register(hide=True)
@cmdutils.argument('win_id', win_id=True)
@cmdutils.argument('count', count=True)
def repeat_command(win_id, count=None):
    """Repeat the last executed command.

    Args:
        count: Which count to pass the command.
    """
    mode_manager = objreg.get('mode-manager', scope='window', window=win_id)
    if mode_manager.mode not in runners.last_command:
        raise cmdexc.CommandError("You didn't do anything yet.")
    cmd = runners.last_command[mode_manager.mode]
    commandrunner = runners.CommandRunner(win_id)
    commandrunner.run(cmd[0], count if count is not None else cmd[1])
