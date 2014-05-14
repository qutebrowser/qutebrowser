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

"""Message singleton so we don't have to define unneeded signals."""

import logging

from PyQt5.QtCore import QObject, pyqtSignal, QCoreApplication


def instance():
    """Get the global messagebridge instance."""
    return QCoreApplication.instance().messagebridge


def error(message):
    """Display an error message in the statusbar."""
    message = str(message)
    logging.error(message)
    instance().error.emit(message)


def info(message):
    """Display a temporary info message in the statusbar."""
    message = str(message)
    logging.info(message)
    instance().info.emit(message)


def text(message):
    """Display a persistent message in the statusbar."""
    message = str(message)
    logging.debug(message)
    instance().text.emit(message)


def clear():
    """Clear a persistent message in the statusbar."""
    instance().text.emit('')


def set_cmd_text(txt):
    """Set the statusbar command line to a preset text."""
    instance().set_cmd_text.emit(txt)


class MessageBridge(QObject):

    """Bridge for messages to be shown in the statusbar."""

    error = pyqtSignal(str)
    info = pyqtSignal(str)
    text = pyqtSignal(str)
    set_cmd_text = pyqtSignal(str)
