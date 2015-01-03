# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtCore import QCoreApplication

from qutebrowser.utils import log, objreg, usertypes
from qutebrowser.commands import cmdutils, runners, cmdexc
from qutebrowser.config import style
from qutebrowser.misc import consolewidget


@cmdutils.register(scope='window', maxsplit=1)
def later(ms: {'type': int}, command, win_id: {'special': 'win_id'}):
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
    except:  # pylint: disable=bare-except
        timer.deleteLater()
        raise


@cmdutils.register(scope='window', maxsplit=1)
def repeat(times: {'type': int}, command, win_id: {'special': 'win_id'}):
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


@cmdutils.register(debug=True)
def debug_crash(typ: {'type': ('exception', 'segfault')}='exception'):
    """Crash for debugging purposes.

    Args:
        typ: either 'exception' or 'segfault'.
    """
    if typ == 'segfault':
        # From python's Lib/test/crashers/bogus_code_obj.py
        co = types.CodeType(0, 0, 0, 0, 0, b'\x04\x71\x00\x00', (), (), (),
                            '', '', 1, b'')
        exec(co)  # pylint: disable=exec-used
        raise Exception("Segfault failed (wat.)")
    else:
        raise Exception("Forced crash")


@cmdutils.register(debug=True)
def debug_all_objects():
    """Print a list of  all objects to the debug log."""
    s = QCoreApplication.instance().get_all_objects()
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
    con_widget.show()
