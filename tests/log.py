# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Logging setup for the tests."""

import logging

from PyQt5.QtCore import (QtDebugMsg, QtWarningMsg, QtCriticalMsg, QtFatalMsg,
                          qInstallMessageHandler)


def init():
    """Initialize logging for the tests."""
    logging.basicConfig(format='\nLOG %(levelname)s %(name)s '
                        '%(module)s:%(funcName)s:%(lineno)d %(message)s',
                        level=logging.WARNING)
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
    qt_to_logging = {
        QtDebugMsg: logging.DEBUG,
        QtWarningMsg: logging.WARNING,
        QtCriticalMsg: logging.ERROR,
        QtFatalMsg: logging.CRITICAL,
    }
    level = qt_to_logging[msg_type]
    # There's very similar code in utils.log, but we want it duplicated here
    # for the tests.
    if context.function is None:
        func = 'none'
    else:
        func = context.function
    if context.category is None or context.category == 'default':
        name = 'qt'
    else:
        name = 'qt-' + context.category
    logger = logging.getLogger('qt-tests')
    record = logger.makeRecord(name, level, context.file, context.line, msg,
                               None, None, func)
    logger.handle(record)
