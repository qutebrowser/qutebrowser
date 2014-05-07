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

from PyQt5.QtGui import QWindow
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QEvent
from PyQt5.QtWidgets import QApplication

import qutebrowser.config.config as config
import qutebrowser.commands.utils as cmdutils
import qutebrowser.utils.debug as debug


def instance():
    """Get the global modeman instance."""
    return QApplication.instance().modeman


def enter(mode):
    """Enter the mode 'mode'."""
    instance().enter(mode)


def leave(mode):
    """Leave the mode 'mode'."""
    instance().leave(mode)


def maybe_leave(mode):
    """Convenience method to leave 'mode' without exceptions."""
    try:
        instance().leave(mode)
    except ValueError:
        pass


class ModeManager(QObject):

    """Manager for keyboard modes.

    Attributes:
        mode: The current mode (readonly property).
        passthrough: A list of modes in which to pass through events.
        mainwindow: The mainwindow object
        _handlers: A dictionary of modes and their handlers.
        _mode_stack: A list of the modes we're currently in, with the active
                     one on the right.
        _forward_unbound_keys: If we should forward unbound keys.
        _releaseevents_to_pass: A list of keys where the keyPressEvent was
                                passed through, so the release event should as
                                well.

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
        self.mainwindow = None
        self._handlers = {}
        self.passthrough = []
        self._mode_stack = []
        self._releaseevents_to_pass = []
        self._forward_unbound_keys = config.get('input',
                                                'forward-unbound-keys')

    @property
    def mode(self):
        """Read-only property for the current mode."""
        if not self._mode_stack:
            return None
        return self._mode_stack[-1]

    def _eventFilter_keypress(self, event):
        """Handle filtering of KeyPress events.

        Args:
            event: The KeyPress to examine.

        Return:
            True if event should be filtered, False otherwise.
        """
        handler = self._handlers[self.mode]
        logging.debug("KeyPress, calling handler {}".format(handler))
        self.key_pressed.emit(event)
        handled = handler(event) if handler is not None else False

        if handled:
            filter_this = True
        elif self.mode in self.passthrough or self._forward_unbound_keys:
            filter_this = False
        else:
            filter_this = True

        if not filter_this:
            self._releaseevents_to_pass.append(event)

        logging.debug("handled: {}, forward-unbound-keys: {}, passthrough: {} "
                      "--> filter: {}".format(handled,
                                              self._forward_unbound_keys,
                                              self.mode in self.passthrough,
                                              filter_this))
        return filter_this

    def _eventFilter_keyrelease(self, event):
        """Handle filtering of KeyRelease events.

        Args:
            event: The KeyPress to examine.

        Return:
            True if event should be filtered, False otherwise.
        """
        # handle like matching KeyPress
        if event in self._releaseevents_to_pass:
            # remove all occurences
            self._releaseevents_to_pass = [
                e for e in self._releaseevents_to_pass if e != event]
            filter_this = False
        else:
            filter_this = True
        logging.debug("KeyRelease --> filter: {}".format(filter_this))
        return filter_this

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

    @cmdutils.register(instance='modeman', name='enter_mode', hide=True)
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

    @cmdutils.register(instance='modeman', name='leave_mode',
                       not_modes=['normal'], hide=True)
    def leave_current_mode(self):
        """Leave the mode we're currently in."""
        if self.mode == 'normal':
            raise ValueError("Can't leave normal mode!")
        self.leave(self.mode)

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Update local setting when config changed."""
        if (section, option) == ('input', 'forward-unbound-keys'):
            self._forward_unbound_keys = config.get('input',
                                                    'forward-unbound-keys')

    def eventFilter(self, obj, event):
        """Filter all events based on the currently set mode.

        Also calls the real keypress handler.

        Args:
            event: The KeyPress to examine.

        Return:
            True if event should be filtered, False otherwise.

        Emit:
            key_pressed: When a key was actually pressed.
        """
        if not hasattr(self, 'mode'):
            # FIXME I have no idea how this could possibly happen, but on
            # Ubuntu it does on startup.
            # self.mode is a simple @property and we certainly don't delete it,
            # so this all makes no sense at all.
            logging.warn("eventFilter called but self.mode doesn't exist!")
            return False
        elif self.mode is None:
            # We got events before mode is set, so just pass them through.
            return False
        typ = event.type()
        if typ not in [QEvent.KeyPress, QEvent.KeyRelease]:
            # We're not interested in non-key-events so we pass them through.
            return False
        if not isinstance(obj, QWindow):
            # We already handled this same event at some point earlier, so
            # we're not interested in it anymore.
            logging.debug("Ignoring event {} for {}".format(
                debug.EVENTS[typ], obj.__class__.__name__))
            return False
        if QApplication.instance().activeWindow() is not self.mainwindow:
            # Some other window (print dialog, etc.) is focused so we pass
            # the event through.
            return False
        logging.debug("Got event {} for {} in mode {}".format(
            debug.EVENTS[typ], obj.__class__.__name__, self.mode))

        if typ == QEvent.KeyPress:
            return self._eventFilter_keypress(event)
        else:
            return self._eventFilter_keyrelease(event)
