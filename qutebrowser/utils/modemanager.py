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

from PyQt5.QtCore import QObject


manager = None


def init(source, parsers=None, parent=None):
    """Initialize the global ModeManager.

    This needs to be done by hand because the import time is before Qt is ready
    for everything.

    Args:
        source: The keypress source signal.
        parsers: A dict of KeyParsers to register.
        parent: Parent to use for ModeManager.
    """
    global manager
    manager = ModeManager(source, parsers, parent)


def enter(mode):
    """Enter the mode 'mode'."""
    manager.enter(mode)


def register(mode, handler):
    """Register a new mode.

    Args:
        mode: The name of the mode.
        handler: Handler for keyPressEvents.
    """
    manager.register(mode, handler)


class ModeManager(QObject):

    """Manager for keyboard modes.

    Attributes:
        _source: The keypress source signal.
        _handlers: A dictionary of modes and their handlers.
        mode: The current mode.
    """

    def __init__(self, sourcesig, parsers=None, parent=None):
        """Constructor.

        Args:
            sourcesig: The signal which gets emitted on a keypress.
            parsers: A list of parsers to register.
        """
        super().__init__(parent)
        self._source = sourcesig
        self._handlers = {}
        self.mode = None
        if parsers is not None:
            for name, parser in parsers.items():
                self._handlers[name] = parser.handle

    def register(self, mode, handler):
        """Register a new mode.

        Args:
            mode: The name of the mode.
            handler: Handler for keyPressEvents.
        """
        self._handlers[mode] = handler

    def enter(self, mode):
        """Enter a new mode."""
        oldmode = self.mode
        logging.debug("Switching mode: {} -> {}".format(oldmode, mode))
        if oldmode is not None:
            try:
                self._source.disconnect(self._handlers[oldmode])
            except TypeError:
                logging.debug("Could not disconnect mode {}".format(oldmode))
        self._source.connect(self._handlers[mode])
        self.mode = mode
