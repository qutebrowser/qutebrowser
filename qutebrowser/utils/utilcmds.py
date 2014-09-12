# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Misc. utility commands exposed to the user."""

import shlex
import types
import functools


from PyQt5.QtCore import QCoreApplication

from qutebrowser.utils import usertypes, log
from qutebrowser.commands import runners, cmdexc, cmdutils
from qutebrowser.config import config, style


_timers = []
_commandrunner = None


def init():
    """Initialize the global _commandrunner."""
    global _commandrunner
    _commandrunner = runners.CommandRunner()


@cmdutils.register()
def later(ms: int, command):
    """Execute a command after some time.

    Args:
        ms: How many milliseconds to wait.
        command: The command to run.
    """
    timer = usertypes.Timer(name='later')
    timer.setSingleShot(True)
    if ms < 0:
        raise cmdexc.CommandError("I can't run something in the past!")
    try:
        timer.setInterval(ms)
    except OverflowError:
        raise cmdexc.CommandError("Numeric argument is too large for internal "
                                  "int representation.")
    _timers.append(timer)
    try:
        cmdline = shlex.split(command)
    except ValueError as e:
        raise cmdexc.CommandError("Could not split command: {}".format(e))
    timer.timeout.connect(functools.partial(
        _commandrunner.run_safely, cmdline))
    timer.timeout.connect(lambda: _timers.remove(timer))
    timer.start()


@cmdutils.register(debug=True)
def debug_crash(typ: ('exception', 'segfault')='exception'):
    """Crash for debugging purposes.

    Args:
        typ: either 'exception' or 'segfault'.

    Raises:
        raises Exception when typ is not segfault.
        segfaults when typ is (you don't say...)
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
def debug_all_widgets():
    """Print a list of all widgets to debug log."""
    s = QCoreApplication.instance().get_all_widgets()
    log.misc.debug(s)


@cmdutils.register(debug=True)
def debug_all_objects():
    """Print a list of  all objects to the debug log."""
    s = QCoreApplication.instance().get_all_objects()
    log.misc.debug(s)


@cmdutils.register(debug=True)
def debug_cache_stats():
    """Print LRU cache stats."""
    config_info = config.instance().get.cache_info()
    style_info = style.get_stylesheet.cache_info()
    log.misc.debug('config: {}'.format(config_info))
    log.misc.debug('style: {}'.format(style_info))
