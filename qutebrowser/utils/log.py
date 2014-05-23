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

"""Loggers and utilities related to logging."""

import logging
from logging import getLogger

# The different loggers used.

statusbar = getLogger('statusbar')
completion = getLogger('completion')
destroy = getLogger('destroy')
modes = getLogger('modes')
webview = getLogger('webview')
mouse = getLogger('mouse')
misc = getLogger('misc')
url = getLogger('url')
procs = getLogger('procs')
commands = getLogger('commands')
init = getLogger('init')
signals = getLogger('signals')
hints = getLogger('hints')
keyboard = getLogger('keyboard')


def init_log(args):
    """Init loggers based on the argparse namespace passed."""
    logfilter = LogFilter(None if args.logfilter is None
                          else args.logfilter.split(','))
    console_handler = logging.StreamHandler()
    console_handler.addFilter(logfilter)
    logging.basicConfig(
        level='DEBUG' if args.debug else args.loglevel.upper(),
        format='%(asctime)s [%(levelname)s] [%(name)s|'
               '%(module)s:%(funcName)s:%(lineno)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[console_handler])


class LogFilter(logging.Filter):

    """Filter to filter log records based on the commandline argument.

    The default Filter only supports one name to show - we support a
    comma-separated list instead.

    Attributes:
        names: A list of names that should be logged.
    """

    def __init__(self, names):
        super().__init__()
        self.names = names

    def filter(self, record):
        """Determine if the specified record is to be logged."""
        if self.names is None:
            return True
        for name in self.names:
            if record.name == name:
                return True
            elif not record.name.startswith(name):
                continue
            elif record.name[len(name)] == '.':
                return True
        return False
