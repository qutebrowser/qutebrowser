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

"""Message singleton so we don't have to define unneeded signals.

Module attributes:
    bridge: The MessageBridge instance.
"""

from PyQt5.QtCore import QObject, pyqtSignal


bridge = None


def init():
    """Initialize the global MessageBridge.

    This needs to be done by hand because the import time is before Qt is ready
    for everything.
    """
    global bridge
    bridge = MessageBridge()


def error(message):
    """Display an error message in the statusbar."""
    bridge.error.emit(message)


def info(message):
    """Display an info message in the statusbar."""
    bridge.info.emit(message)


class MessageBridge(QObject):

    """Bridge for messages to be shown in the statusbar."""

    error = pyqtSignal(str)
    info = pyqtSignal(str)
