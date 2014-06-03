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

import re
import os
import sys
import logging
from logging import getLogger
from collections import deque

from PyQt5.QtCore import (QtDebugMsg, QtWarningMsg, QtCriticalMsg, QtFatalMsg,
                          qInstallMessageHandler)
try:
    # pylint: disable=import-error
    from colorlog import ColoredFormatter
except ImportError:
    ColoredFormatter = None

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
js = getLogger('js')
qt = getLogger('qt')


ram_handler = None


def init_log(args):
    """Init loggers based on the argparse namespace passed."""
    global ram_handler
    logfilter = LogFilter(None if args.logfilter is None
                          else args.logfilter.split(','))
    level = 'DEBUG' if args.debug else args.loglevel.upper()
    try:
        numeric_level = getattr(logging, level)
    except AttributeError:
        raise ValueError("Invalid log level: {}".format(args.loglevel))
    simple_fmt = '{levelname}: {message}'
    extended_fmt = ('{asctime:8} {levelname:8} {name:10} {module}:{funcName}:'
                    '{lineno} {message}')
    simple_fmt_colored = '%(log_color)s%(levelname)s%(reset)s: %(message)s'
    extended_fmt_colored = ('%(green)s%(asctime)-8s%(reset)s '
                            '%(log_color)s%(levelname)-8s%(reset)s '
                            '%(yellow)s%(name)-10s %(module)s:%(funcName)s:'
                            '%(lineno)s%(reset)s %(message)s')
    datefmt = '%H:%M:%S'

    if numeric_level <= logging.DEBUG:
        console_fmt = extended_fmt
        console_fmt_colored = extended_fmt_colored
    else:
        console_fmt = simple_fmt
        console_fmt_colored = simple_fmt_colored
    if (ColoredFormatter is not None and os.name == 'posix' and
            sys.stderr.isatty() and args.color):
        console_formatter = ColoredFormatter(
            console_fmt_colored, datefmt, log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red',
            }
        )
    else:
        console_formatter = logging.Formatter(console_fmt, datefmt, '{')
    console_handler = logging.StreamHandler()
    console_handler.addFilter(logfilter)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)

    ram_formatter = logging.Formatter(extended_fmt, datefmt, '{')
    ram_handler = RAMHandler(capacity=500)
    ram_handler.setLevel(logging.NOTSET)
    ram_handler.setFormatter(ram_formatter)

    root = getLogger()
    root.addHandler(console_handler)
    root.addHandler(ram_handler)
    root.setLevel(logging.NOTSET)

    logging.captureWarnings(True)
    qInstallMessageHandler(qt_message_handler)


def qt_message_handler(msg_type, context, msg):
    """Qt message handler to redirect qWarning etc. to the logging system.

    Args:
        QtMsgType msg_type: The level of the message.
        QMessageLogContext context: The source code location of the message.
        msg: The message text.
    """
    # Mapping from Qt logging levels to the matching logging module levels.
    # Note we map critical to ERROR as it's actually "just" an error, and fatal
    # to critical.
    QT_TO_LOGGING = {
        QtDebugMsg: logging.DEBUG,
        QtWarningMsg: logging.WARNING,
        QtCriticalMsg: logging.ERROR,
        QtFatalMsg: logging.CRITICAL,
    }
    # Suppress some messages because they're well-known.
    SUPPRESSED_MSGS = ['libpng warning: iCCP: Not recognizing known sRGB '
                       'profile that has been edited']
    if msg in SUPPRESSED_MSGS:
        return
    # We get something like "void qt_png_warning(png_structp, png_const_charp)"
    # from Qt, but only want "qt_png_warning".
    match = re.match(r'\w* (\w*)\(.*\)', context.function)
    if match is not None:
        func = match.group(1)
    else:
        func = context.function
    name = 'qt' if context.category == 'default' else 'qt-' + context.category
    record = qt.makeRecord(name, QT_TO_LOGGING[msg_type], context.file,
                           context.line, msg, None, None, func)
    qt.handle(record)


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


class RAMHandler(logging.Handler):

    """Logging handler which keeps the messages in a deque in RAM.

    Loosly based on logging.BufferingHandler which is unsuitable because it
    uses a simple list rather than a deque.

    Attributes:
        data: A deque containing the logging records.
    """

    def __init__(self, capacity):
        super().__init__()
        self.data = deque(maxlen=capacity)

    def emit(self, record):
        self.data.append(record)

    def dump_log(self):
        """Dump the complete formatted log data as as string."""
        lines = []
        for record in self.data:
            lines.append(self.format(record))
        return '\n'.join(lines)
