# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

from PyQt5.QtGui import QWindow
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QEvent
from PyQt5.QtWidgets import QApplication

from qutebrowser.config import config
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.utils import usertypes, log, utils


class ModeLockedError(Exception):

    """Exception raised when the mode is currently locked."""


def enter(mode, reason=None):
    """Enter the mode 'mode'."""
    utils.get_object('mode-manager').enter(mode, reason)


def leave(mode, reason=None):
    """Leave the mode 'mode'."""
    utils.get_object('mode-manager').leave(mode, reason)


def maybe_enter(mode, reason=None):
    """Convenience method to enter 'mode' without exceptions."""
    try:
        utils.get_object('mode-manager').enter(mode, reason)
    except ModeLockedError:
        pass


def maybe_leave(mode, reason=None):
    """Convenience method to leave 'mode' without exceptions."""
    try:
        utils.get_object('mode-manager').leave(mode, reason)
    except ValueError as e:
        # This is rather likely to happen, so we only log to debug log.
        log.modes.debug(e)


class ModeManager(QObject):

    """Manager for keyboard modes.

    Attributes:
        passthrough: A list of modes in which to pass through events.
        locked: Whether current mode is locked. This means the current mode can
                still be left (then locked will be reset), but no new mode can
                be entered while the current mode is active.
        _handlers: A dictionary of modes and their handlers.
        _mode_stack: A list of the modes we're currently in, with the active
                     one on the right.
        _forward_unbound_keys: If we should forward unbound keys.
        _releaseevents_to_pass: A list of keys where the keyPressEvent was
                                passed through, so the release event should as
                                well.

    Signals:
        entered: Emitted when a mode is entered.
                 arg: The mode which has been entered.
        left:  Emitted when a mode is left.
                 arg: The mode which has been left.
    """

    entered = pyqtSignal(usertypes.KeyMode)
    left = pyqtSignal(usertypes.KeyMode)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.locked = False
        self._handlers = {}
        self.passthrough = []
        self._mode_stack = []
        self._releaseevents_to_pass = []
        self._forward_unbound_keys = config.get('input',
                                                'forward-unbound-keys')

    def __repr__(self):
        return '<{} mode={}>'.format(self.__class__.__name__, self.mode())

    def mode(self):
        """Get the current mode.."""
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
        curmode = self.mode()
        handler = self._handlers[curmode]
        if curmode != usertypes.KeyMode.insert:
            log.modes.debug("got keypress in mode {} - calling handler "
                            "{}".format(curmode, handler.__qualname__))
        handled = handler(event) if handler is not None else False

        is_non_alnum = bool(event.modifiers()) or not event.text().strip()

        if handled:
            filter_this = True
        elif (curmode in self.passthrough or
                self._forward_unbound_keys == 'all' or
                (self._forward_unbound_keys == 'auto' and is_non_alnum)):
            filter_this = False
        else:
            filter_this = True

        if not filter_this:
            self._releaseevents_to_pass.append(event)

        if curmode != usertypes.KeyMode.insert:
            log.modes.debug("handled: {}, forward-unbound-keys: {}, "
                            "passthrough: {}, is_non_alnum: {} --> filter: "
                            "{}".format(handled, self._forward_unbound_keys,
                                        curmode in self.passthrough,
                                        is_non_alnum, filter_this))
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
        if self.mode() != usertypes.KeyMode.insert:
            log.modes.debug("filter: {}".format(filter_this))
        return filter_this

    def register(self, mode, handler, passthrough=False):
        """Register a new mode.

        Args:
            mode: The name of the mode.
            handler: Handler for keyPressEvents.
            passthrough: Whether to pass keybindings in this mode through to
                         the widgets.
        """
        if not isinstance(mode, usertypes.KeyMode):
            raise TypeError("Mode {} is no KeyMode member!".format(mode))
        self._handlers[mode] = handler
        if passthrough:
            self.passthrough.append(mode)

    def enter(self, mode, reason=None):
        """Enter a new mode.

        Args:
            mode: The mode to enter as a KeyMode member.
            reason: Why the mode was entered.

        Emit:
            entered: With the new mode name.
        """
        if not isinstance(mode, usertypes.KeyMode):
            raise TypeError("Mode {} is no KeyMode member!".format(mode))
        if self.locked:
            log.modes.debug("Not entering mode {} because mode is locked to "
                            "{}.".format(mode, self.mode()))
            raise ModeLockedError("Mode is currently locked to {}".format(
                self.mode()))
        log.modes.debug("Entering mode {}{}".format(
            mode, '' if reason is None else ' (reason: {})'.format(reason)))
        if mode not in self._handlers:
            raise ValueError("No handler for mode {}".format(mode))
        if self._mode_stack and self._mode_stack[-1] == mode:
            log.modes.debug("Already at end of stack, doing nothing")
            return
        self._mode_stack.append(mode)
        log.modes.debug("New mode stack: {}".format(self._mode_stack))
        self.entered.emit(mode)

    @cmdutils.register(instance='mode-manager', hide=True)
    def enter_mode(self, mode):
        """Enter a key mode.

        Args:
            mode: The mode to enter.
        """
        try:
            m = usertypes.KeyMode[mode]
        except KeyError:
            raise cmdexc.CommandError("Mode {} does not exist!".format(mode))
        self.enter(m, 'command')

    def leave(self, mode, reason=None):
        """Leave a key mode.

        Args:
            mode: The name of the mode to leave.
            reason: Why the mode was left.

        Emit:
            left: With the old mode name.
        """
        try:
            self._mode_stack.remove(mode)
        except ValueError:
            raise ValueError("Mode {} not on mode stack!".format(mode))
        self.locked = False
        log.modes.debug("Leaving mode {}{}, new mode stack {}".format(
            mode, '' if reason is None else ' (reason: {})'.format(reason),
            self._mode_stack))
        self.left.emit(mode)

    @cmdutils.register(instance='mode-manager', name='leave-mode',
                       not_modes=[usertypes.KeyMode.normal], hide=True)
    def leave_current_mode(self):
        """Leave the mode we're currently in."""
        if self.mode() == usertypes.KeyMode.normal:
            raise ValueError("Can't leave normal mode!")
        self.leave(self.mode(), 'leave current')

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
        """
        if self.mode() is None:
            # We got events before mode is set, so just pass them through.
            return False
        typ = event.type()
        if typ not in [QEvent.KeyPress, QEvent.KeyRelease]:
            # We're not interested in non-key-events so we pass them through.
            return False
        if not isinstance(obj, QWindow):
            # We already handled this same event at some point earlier, so
            # we're not interested in it anymore.
            return False
        if (QApplication.instance().activeWindow() is not
                utils.get_object('main-window')):
            # Some other window (print dialog, etc.) is focused so we pass
            # the event through.
            return False

        if typ == QEvent.KeyPress:
            return self._eventFilter_keypress(event)
        else:
            return self._eventFilter_keyrelease(event)
