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

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QEvent

import qutebrowser.config.config as config
import qutebrowser.commands.utils as cmdutils
import qutebrowser.utils.debug as debug


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


def leave(mode):
    """Leave the mode 'mode'."""
    manager.leave(mode)


def maybe_leave(mode):
    """Convenience method to leave 'mode' without exceptions."""
    try:
        manager.leave(mode)
    except ValueError:
        pass


class ModeManager(QObject):

    """Manager for keyboard modes.

    Attributes:
        mode: The current mode (readonly property).
        passthrough: A list of modes in which to pass through events.
        _handlers: A dictionary of modes and their handlers.
        _mode_stack: A list of the modes we're currently in, with the active
                     one on the right.
        _forward_unbound_keys: If we should forward unbound keys.

    Signals:
        entered: Emitted when a mode is entered.
                 arg: Name of the entered mode.
        left:  Emitted when a mode is left.
                 arg: Name of the left mode.
        key_pressed: A key was pressed.
    """

    entered = pyqtSignal(str)
    left = pyqtSignal(str)
    key_pressed = pyqtSignal('QKeyEvent')

    def __init__(self, parent=None):
        super().__init__(parent)
        self._handlers = {}
        self.passthrough = []
        self._mode_stack = []
        self._forward_unbound_keys = config.get('general',
                                                'forward_unbound_keys')

    @property
    def mode(self):
        """Read-only property for the current mode."""
        if not self._mode_stack:
            return None
        return self._mode_stack[-1]

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
            self.passthrough.append(mode)

    def enter(self, mode):
        """Enter a new mode.

        Args:
            mode; The name of the mode to enter.

        Emit:
            entered: With the new mode name.
        """
        logging.debug("Switching mode to {}".format(mode))
        if mode not in self._handlers:
            raise ValueError("No handler for mode {}".format(mode))
        if self._mode_stack and self._mode_stack[-1] == mode:
            logging.debug("Already at end of stack, doing nothing")
            return
        self._mode_stack.append(mode)
        logging.debug("New mode stack: {}".format(self._mode_stack))
        self.entered.emit(mode)

    def leave(self, mode):
        """Leave a mode.

        Args:
            mode; The name of the mode to leave.

        Emit:
            left: With the old mode name.
        """
        try:
            self._mode_stack.remove(mode)
        except ValueError:
            raise ValueError("Mode {} not on mode stack!".format(mode))
        logging.debug("Leaving mode {}".format(mode))
        logging.debug("New mode stack: {}".format(self._mode_stack))
        self.left.emit(mode)

    # FIXME handle modes=[] and not_modes=[] params
    @cmdutils.register(instance='modeman', name='leave_mode', hide=True)
    def leave_current_mode(self):
        if self.mode == "normal":
            raise ValueError("Can't leave normal mode!")
        self.leave(self.mode)

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update local setting when config changed."""
        if (section, option) == ('general', 'forward_unbound_keys'):
            self._forward_unbound_keys = config.get('general',
                                                    'forward_unbound_keys')

    def eventFilter(self, _obj, evt):
        """Filter all events based on the currently set mode.

        Also calls the real keypress handler.

        Emit:
            key_pressed: When a key was actually pressed.
        """
        if self.mode is None:
            # We got events before mode is set, so just pass them through.
            return False
        handler = self._handlers[self.mode]
        typ = evt.type()
        if typ not in [QEvent.KeyPress, QEvent.KeyRelease]:
            # We're not interested in non-key-events so we pass them through.
            return False
        logging.debug("Got event {} for {}".format(debug.EVENTS[typ], _obj))
        if self.mode in self.passthrough:
            # We're currently in a passthrough mode so we pass everything
            # through.*and* let the passthrough keyhandler know.
            # FIXME what if we leave the passthrough mode right here?
            self.key_pressed.emit(evt)
            if handler is not None:
                handler(evt)
            return False
        elif typ == QEvent.KeyPress:
            # KeyPress in a non-passthrough mode - call handler and filter
            # event from widgets (unless unhandled and configured to pass
            # unhandled events through)
            self.key_pressed.emit(evt)
            if handler is not None:
                handled = handler(evt)
            else:
                handled = False
            if handled or not self._forward_unbound_keys:
                return True
            else:
                return True
        else:
            # KeyRelease in a non-passthrough mode - filter event and ignore it
            # entirely.
            return True
