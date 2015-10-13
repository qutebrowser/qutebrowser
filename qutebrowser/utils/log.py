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

"""Loggers and utilities related to logging."""

import os
import sys
import html as pyhtml
import logging
import contextlib
import collections
import faulthandler
import traceback
import warnings

from PyQt5 import QtCore
# Optional imports
try:
    import colorama
except ImportError:
    colorama = None
try:
    import colorlog
except ImportError:
    colorlog = None
else:
    # WORKAROUND
    # colorlog calls colorama.init() which we don't want, also it breaks our
    # sys.stdout/sys.stderr if they are None. Bugreports:
    # https://code.google.com/p/colorama/issues/detail?id=61
    # https://github.com/borntyping/python-colorlog/issues/13
    # This should be (partially) fixed in colorama 0.3.2.
    # (stream only gets wrapped if it's not None)
    if colorama is not None:
        colorama.deinit()

# Log formats to use.
SIMPLE_FMT = '{levelname}: {message}'
EXTENDED_FMT = ('{asctime:8} {levelname:8} {name:10} {module}:{funcName}:'
                '{lineno} {message}')
SIMPLE_FMT_COLORED = '%(log_color)s%(levelname)s%(reset)s: %(message)s'
EXTENDED_FMT_COLORED = (
    '%(green)s%(asctime)-8s%(reset)s '
    '%(log_color)s%(levelname)-8s%(reset)s '
    '%(cyan)s%(name)-10s %(module)s:%(funcName)s:%(lineno)s%(reset)s '
    '%(log_color)s%(message)s%(reset)s'
)
EXTENDED_FMT_HTML = (
    '<tr>'
    '<td><pre>%(green)s%(asctime)-8s%(reset)s</pre></td>'
    '<td><pre>%(log_color)s%(levelname)-8s%(reset)s</pre></td>'
    '<td></pre>%(cyan)s%(name)-10s</pre></td>'
    '<td><pre>%(cyan)s%(module)s:%(funcName)s:%(lineno)s%(reset)s</pre></td>'
    '<td><pre>%(log_color)s%(message)s%(reset)s</pre></td>'
    '</tr>'
)
DATEFMT = '%H:%M:%S'
LOG_COLORS = {
    'VDEBUG': 'white',
    'DEBUG': 'white',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'red',
}


# We first monkey-patch logging to support our VDEBUG level before getting the
# loggers.  Based on http://stackoverflow.com/a/13638084
VDEBUG_LEVEL = 9
logging.addLevelName(VDEBUG_LEVEL, 'VDEBUG')
logging.VDEBUG = VDEBUG_LEVEL


def vdebug(self, msg, *args, **kwargs):
    """Log with a VDEBUG level.

    VDEBUG is used when a debug message is rather verbose, and probably of
    little use to the end user or for post-mortem debugging, i.e. the content
    probably won't change unless the code changes.
    """
    if self.isEnabledFor(VDEBUG_LEVEL):
        # pylint: disable=protected-access
        self._log(VDEBUG_LEVEL, msg, args, **kwargs)


logging.Logger.vdebug = vdebug


# The different loggers used.
statusbar = logging.getLogger('statusbar')
completion = logging.getLogger('completion')
destroy = logging.getLogger('destroy')
modes = logging.getLogger('modes')
webview = logging.getLogger('webview')
mouse = logging.getLogger('mouse')
misc = logging.getLogger('misc')
url = logging.getLogger('url')
procs = logging.getLogger('procs')
commands = logging.getLogger('commands')
init = logging.getLogger('init')
signals = logging.getLogger('signals')
hints = logging.getLogger('hints')
keyboard = logging.getLogger('keyboard')
downloads = logging.getLogger('downloads')
js = logging.getLogger('js')  # Javascript console messages
qt = logging.getLogger('qt')  # Warnings produced by Qt
rfc6266 = logging.getLogger('rfc6266')
ipc = logging.getLogger('ipc')
shlexer = logging.getLogger('shlexer')
save = logging.getLogger('save')
message = logging.getLogger('message')
config = logging.getLogger('config')
sessions = logging.getLogger('sessions')


ram_handler = None


def init_log(args):
    """Init loggers based on the argparse namespace passed."""
    level = 'VDEBUG' if args.debug else args.loglevel.upper()
    try:
        numeric_level = getattr(logging, level)
    except AttributeError:
        raise ValueError("Invalid log level: {}".format(args.loglevel))

    console, ram = _init_handlers(numeric_level, args.color, args.loglines)
    root = logging.getLogger()
    if console is not None:
        if args.logfilter is not None:
            console.addFilter(LogFilter(args.logfilter.split(',')))
        root.addHandler(console)
    if ram is not None:
        root.addHandler(ram)
    root.setLevel(logging.NOTSET)
    logging.captureWarnings(True)
    warnings.simplefilter('default')
    QtCore.qInstallMessageHandler(qt_message_handler)


@contextlib.contextmanager
def disable_qt_msghandler():
    """Contextmanager which temporarily disables the Qt message handler."""
    old_handler = QtCore.qInstallMessageHandler(None)
    try:
        yield
    finally:
        QtCore.qInstallMessageHandler(old_handler)


def _init_handlers(level, color, ram_capacity):
    """Init log handlers.

    Args:
        level: The numeric logging level.
        color: Whether to use color if available.
    """
    global ram_handler
    console_fmt, ram_fmt, html_fmt, use_colorama = _init_formatters(
        level, color)

    if sys.stderr is None:
        console_handler = None
    else:
        if use_colorama:
            stream = colorama.AnsiToWin32(sys.stderr)
        else:
            stream = sys.stderr
        console_handler = logging.StreamHandler(stream)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_fmt)

    if ram_capacity == 0:
        ram_handler = None
    else:
        ram_handler = RAMHandler(capacity=ram_capacity)
        ram_handler.setLevel(logging.NOTSET)
        ram_handler.setFormatter(ram_fmt)
        ram_handler.html_formatter = html_fmt

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
    ram_formatter = logging.Formatter(EXTENDED_FMT, DATEFMT, '{')
    html_formatter = HTMLFormatter(EXTENDED_FMT_HTML, DATEFMT,
                                   log_colors=LOG_COLORS)
    if sys.stderr is None:
        return None, ram_formatter, html_formatter, False
    use_colorama = False
    if (colorlog is not None and (os.name == 'posix' or colorama) and
            sys.stderr.isatty() and color):
        console_formatter = colorlog.ColoredFormatter(
            console_fmt_colored, DATEFMT, log_colors=LOG_COLORS)
        if colorama:
            use_colorama = True
    else:
        console_formatter = logging.Formatter(console_fmt, DATEFMT, '{')
    return console_formatter, ram_formatter, html_formatter, use_colorama


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
        QtCore.QtDebugMsg: logging.DEBUG,
        QtCore.QtWarningMsg: logging.WARNING,
        QtCore.QtCriticalMsg: logging.ERROR,
        QtCore.QtFatalMsg: logging.CRITICAL,
    }
    try:
        # pylint: disable=no-member
        qt_to_logging[QtCore.QtInfoMsg] = logging.INFO
    except AttributeError:
        # Qt < 5.5
        pass

    # Change levels of some well-known messages to debug so they don't get
    # shown to the user.
    #
    # If a message starts with any text in suppressed_msgs, it's not logged as
    # error.
    suppressed_msgs = [
        # PNGs in Qt with broken color profile
        # https://bugreports.qt.io/browse/QTBUG-39788
        'libpng warning: iCCP: Not recognizing known sRGB profile that has '
            'been edited',  # noqa
        # Hopefully harmless warning
        'OpenType support missing for script ',
        # Error if a QNetworkReply gets two different errors set. Harmless Qt
        # bug on some pages.
        # https://bugreports.qt.io/browse/QTBUG-30298
        'QNetworkReplyImplPrivate::error: Internal problem, this method must '
            'only be called once.',
        # Sometimes indicates missing text, but most of the time harmless
        'load glyph failed ',
        # Harmless, see https://bugreports.qt.io/browse/QTBUG-42479
        'content-type missing in HTTP POST, defaulting to '
            'application/x-www-form-urlencoded. '
            'Use QNetworkRequest::setHeader() to fix this problem.',
        # https://bugreports.qt.io/browse/QTBUG-43118
        'Using blocking call!',
        # Hopefully harmless
        '"Method "GetAll" with signature "s" on interface '
            '"org.freedesktop.DBus.Properties" doesn\'t exist',
        'WOFF support requires QtWebKit to be built with zlib support.',
        # Weird Enlightment/GTK X extensions
        'QXcbWindow: Unhandled client message: "_E_',
        'QXcbWindow: Unhandled client message: "_ECORE_',
        'QXcbWindow: Unhandled client message: "_GTK_',
        # Happens on AppVeyor CI
        'SetProcessDpiAwareness failed:',
    ]
    if sys.platform == 'darwin':
        suppressed_msgs += [
            'libpng warning: iCCP: known incorrect sRGB profile',
            # https://bugreports.qt.io/browse/QTBUG-47154
            'virtual void QSslSocketBackendPrivate::transmit() SSLRead failed '
                'with: -9805',  # noqa
        ]

    if any(msg.strip().startswith(pattern) for pattern in suppressed_msgs):
        level = logging.DEBUG
    else:
        level = qt_to_logging[msg_type]
    if context.function is None:
        func = 'none'
    else:
        func = context.function
    if context.category is None or context.category == 'default':
        name = 'qt'
    else:
        name = 'qt-' + context.category
    if msg.splitlines()[0] == ('This application failed to start because it '
                               'could not find or load the Qt platform plugin '
                               '"xcb".'):
        # Handle this message specially.
        msg += ("\n\nOn Archlinux, this should fix the problem:\n"
                "    pacman -S libxkbcommon-x11")
        faulthandler.disable()
    stack = ''.join(traceback.format_stack())
    record = qt.makeRecord(name, level, context.file, context.line, msg, None,
                           None, func, sinfo=stack)
    qt.handle(record)


@contextlib.contextmanager
def hide_qt_warning(pattern, logger='qt'):
    """Hide Qt warnings matching the given regex."""
    log_filter = QtWarningFilter(pattern)
    logger_obj = logging.getLogger(logger)
    logger_obj.addFilter(log_filter)
    try:
        yield
    finally:
        logger_obj.removeFilter(log_filter)


class QtWarningFilter(logging.Filter):

    """Filter to filter Qt warnings.

    Attributes:
        _pattern: The start of the message.
    """

    def __init__(self, pattern):
        super().__init__()
        self._pattern = pattern

    def filter(self, record):
        """Determine if the specified record is to be logged."""
        if record.msg.strip().startswith(self._pattern):
            return False  # filter
        else:
            return True  # log


class LogFilter(logging.Filter):

    """Filter to filter log records based on the commandline argument.

    The default Filter only supports one name to show - we support a
    comma-separated list instead.

    Attributes:
        _names: A list of names that should be logged.
    """

    def __init__(self, names):
        super().__init__()
        self._names = names

    def filter(self, record):
        """Determine if the specified record is to be logged."""
        if self._names is None:
            return True
        if record.levelno > logging.DEBUG:
            # More important than DEBUG, so we won't filter at all
            return True
        for name in self._names:
            if record.name == name:
                return True
            elif not record.name.startswith(name):
                continue
            elif record.name[len(name)] == '.':
                return True
        return False


class RAMHandler(logging.Handler):

    """Logging handler which keeps the messages in a deque in RAM.

    Loosely based on logging.BufferingHandler which is unsuitable because it
    uses a simple list rather than a deque.

    Attributes:
        _data: A deque containing the logging records.
    """

    def __init__(self, capacity):
        super().__init__()
        self.html_formatter = None
        if capacity != -1:
            self._data = collections.deque(maxlen=capacity)
        else:
            self._data = collections.deque()

    def emit(self, record):
        if record.levelno >= logging.DEBUG:
            # We don't log VDEBUG to RAM.
            self._data.append(record)

    def dump_log(self, html=False):
        """Dump the complete formatted log data as as string.

        FIXME: We should do all the HTML formatter via jinja2.
        (probably obsolete when moving to a widget for logging,
        https://github.com/The-Compiler/qutebrowser/issues/34
        """
        lines = []
        fmt = self.html_formatter.format if html else self.format
        self.acquire()
        try:
            records = list(self._data)
        finally:
            self.release()
        for record in records:
            lines.append(fmt(record))
        return '\n'.join(lines)


class HTMLFormatter(logging.Formatter):

    """Formatter for HTML-colored log messages, similar to colorlog.

    Attributes:
        _log_colors: The colors to use for logging levels.
        _colordict: The colordict passed to the logger.
    """

    def __init__(self, fmt, datefmt, log_colors):
        """Constructor.

        Args:
            fmt: The format string to use.
            datefmt: The date format to use.
            log_colors: The colors to use for logging levels.
        """
        super().__init__(fmt, datefmt)
        self._log_colors = log_colors
        self._colordict = {}
        # We could solve this nicer by using CSS, but for this simple case this
        # works.
        for color in ['black', 'red', 'green', 'yellow', 'blue', 'purple',
                      'cyan', 'white']:
            self._colordict[color] = '<font color="{}">'.format(color)
        self._colordict['reset'] = '</font>'

    def format(self, record):
        record.__dict__.update(self._colordict)
        if record.levelname in self._log_colors:
            color = self._log_colors[record.levelname]
            record.log_color = self._colordict[color]
        else:
            record.log_color = ''
        for field in ['msg', 'filename', 'funcName', 'levelname', 'module',
                      'name', 'pathname', 'processName', 'threadName']:
            data = str(getattr(record, field))
            setattr(record, field, pyhtml.escape(data))
        msg = super().format(record)
        if not msg.endswith(self._colordict['reset']):
            msg += self._colordict['reset']
        return msg

    def formatTime(self, record, datefmt=None):
        out = super().formatTime(record, datefmt)
        return pyhtml.escape(out)
