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

"""Mode manager singleton which handles the current keyboard mode.

Module attributes:
    manager: The ModeManager instance.
"""

import logging

from PyQt5.QtCore import pyqtSignal, QObject, QEvent


manager = None


def init(parent=None):
    """Initialize the global ModeManager.

    This needs to be done by hand because the import time is before Qt is ready
    for everything.

    Args:
        parent: Parent to use for ModeManager.
    """
    global manager
    manager = ModeManager(parent)


def enter(mode):
    """Enter the mode 'mode'."""
    manager.enter(mode)


class ModeManager(QObject):

    """Manager for keyboard modes.

    Attributes:
        _handlers: A dictionary of modes and their handlers.
        _passthrough: A list of modes in which to pass through events.
        mode: The current mode.

    Signals:
        entered: Emitted when a mode is entered.
                 arg: Name of the entered mode.
        leaved:  Emitted when a mode is leaved.
                 arg: Name of the leaved mode.
    """

    entered = pyqtSignal(str)
    leaved = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._handlers = {}
        self._passthrough = []
        self.mode = None

    def register(self, mode, handler, passthrough=False):
        """Register a new mode.

        Args:
            mode: The name of the mode.
            handler: Handler for keyPressEvents.
            passthrough: Whether to pass keybindings in this mode through to
                         the widgets.
        """
        self._handlers[mode] = handler
        if passthrough:
            self._passthrough.append(mode)

    def enter(self, mode):
        """Enter a new mode.

        Emit:
            leaved: With the old mode name.
            entered: With the new mode name.
        """
        oldmode = self.mode
        logging.debug("Switching mode: {} -> {}".format(oldmode, mode))
        if mode not in self._handlers:
            raise ValueError("No handler for mode {}".format(mode))
        if oldmode is not None:
            self.leaved.emit(oldmode)
        self.mode = mode
        self.entered.emit(mode)

    def eventFilter(self, obj, evt):
        if evt.type() not in [QEvent.KeyPress, QEvent.KeyRelease]:
            return False
        elif self.mode == "insert":
            return False
        elif evt.type() == QEvent.KeyPress:
            self._handlers[self.mode](evt)
            return True
        else:
            return True
