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
# Optional imports
try:
    # pylint: disable=import-error
    from colorlog import ColoredFormatter
except ImportError:
    ColoredFormatter = None
try:
    # pylint: disable=import-error
    import colorama
except ImportError:
    colorama = None

# Log formats to use.
SIMPLE_FMT = '{levelname}: {message}'
EXTENDED_FMT = ('{asctime:8} {levelname:8} {name:10} {module}:{funcName}:'
                '{lineno} {message}')
SIMPLE_FMT_COLORED = '%(log_color)s%(levelname)s%(reset)s: %(message)s'
EXTENDED_FMT_COLORED = ('%(green)s%(asctime)-8s%(reset)s %(log_color)'
                        's%(levelname)-8s%(reset)s %(yellow)s%(name)-10s '
                        '%(module)s:%(funcName)s:%(lineno)s%(reset)s '
                        '%(message)s')
DATEFMT = '%H:%M:%S'


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
    level = 'DEBUG' if args.debug else args.loglevel.upper()
    try:
        numeric_level = getattr(logging, level)
    except AttributeError:
        raise ValueError("Invalid log level: {}".format(args.loglevel))

    console, ram = _init_handlers(numeric_level, args.color)
    if args.logfilter is not None and numeric_level <= logging.DEBUG:
        console.addFilter(LogFilter(args.logfilter.split(',')))
    root = getLogger()
    root.addHandler(console)
    root.addHandler(ram)
    root.setLevel(logging.NOTSET)
    logging.captureWarnings(True)
    qInstallMessageHandler(qt_message_handler)


def _init_handlers(level, color):
    """Init log handlers.

    Args:
        level: The numeric logging level.
        color: Whether to use color if available.
    """
    global ram_handler
    console_formatter, ram_formatter, use_colorama = _init_formatters(
        level, color)

    if use_colorama:
        stream = colorama.AnsiToWin32(sys.stderr)
    else:
        stream = sys.stderr
    console_handler = logging.StreamHandler(stream)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)

    ram_handler = RAMHandler(capacity=500)
    ram_handler.setLevel(logging.NOTSET)
    ram_handler.setFormatter(ram_formatter)

    return console_handler, ram_handler


def _init_formatters(level, color):
    """Init log formatters.

    Args:
        level: The numeric logging level.
        color: Whether to use color if available.

    Return:
        A (console_formatter, ram_formatter, use_colorama) tuple.
        console_formatter/ram_formatter: logging.Formatter instances.
        use_colorama: Whether to use colorama.
    """
    if level <= logging.DEBUG:
        console_fmt = EXTENDED_FMT
        console_fmt_colored = EXTENDED_FMT_COLORED
    else:
        console_fmt = SIMPLE_FMT
        console_fmt_colored = SIMPLE_FMT_COLORED
    use_colorama = False
    if (ColoredFormatter is not None and (os.name == 'posix' or colorama) and
            sys.stderr.isatty() and color):
        console_formatter = ColoredFormatter(
            console_fmt_colored, DATEFMT, log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red',
            }
        )
        if colorama:
            colorama.init()
            use_colorama = True
    else:
        console_formatter = logging.Formatter(console_fmt, DATEFMT, '{')
    ram_formatter = logging.Formatter(EXTENDED_FMT, DATEFMT, '{')
    return console_formatter, ram_formatter, use_colorama


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
    qt_to_logging = {
        QtDebugMsg: logging.DEBUG,
        QtWarningMsg: logging.WARNING,
        QtCriticalMsg: logging.ERROR,
        QtFatalMsg: logging.CRITICAL,
    }
    # Change levels of some well-known messages to debug so they don't get
    # shown to the user.
    # suppressed_msgs is a list of regexes matching the message texts to hide.
    suppressed_msgs = ["libpng warning: iCCP: Not recognizing known sRGB "
                       "profile that has been edited",
                       "OpenType support missing for script [0-9]*"]
    if any(re.match(pattern, msg.strip()) for pattern in suppressed_msgs):
        level = logging.DEBUG
    else:
        level = qt_to_logging[msg_type]
    # We get something like "void qt_png_warning(png_structp, png_const_charp)"
    # from Qt, but only want "qt_png_warning".
    match = re.match(r'.*( |::)(\w*)\(.*\)', context.function)
    if match is not None:
        func = match.group(2)
    else:
        func = context.function
    name = 'qt' if context.category == 'default' else 'qt-' + context.category
    record = qt.makeRecord(name, level, context.file, context.line, msg, None,
                           None, func)
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
        if record.levelno > logging.DEBUG:
            # More important than DEBUG, so we won't filter at all
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
