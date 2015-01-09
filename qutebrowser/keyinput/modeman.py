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

"""Mode manager singleton which handles the current keyboard mode.

Module attributes:
    manager: The ModeManager instance.
"""

import functools

from PyQt5.QtGui import QWindow
from PyQt5.QtCore import pyqtSignal, QObject, QEvent
from PyQt5.QtWidgets import QApplication

from qutebrowser.keyinput import modeparsers, keyparser
from qutebrowser.config import config
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.utils import usertypes, log, objreg, utils


class NotInModeError(Exception):

    """Exception raised when we want to leave a mode we're not in."""


def init(win_id, parent):
    """Initialize the mode manager and the keyparsers for the given win_id."""
    KM = usertypes.KeyMode  # pylint: disable=invalid-name
    modeman = ModeManager(win_id, parent)
    objreg.register('mode-manager', modeman, scope='window', window=win_id)
    keyparsers = {
        KM.normal: modeparsers.NormalKeyParser(win_id, modeman),
        KM.hint: modeparsers.HintKeyParser(win_id, modeman),
        KM.insert: keyparser.PassthroughKeyParser(win_id, 'insert', modeman),
        KM.passthrough: keyparser.PassthroughKeyParser(win_id, 'passthrough',
                                                       modeman),
        KM.command: keyparser.PassthroughKeyParser(win_id, 'command', modeman),
        KM.prompt: keyparser.PassthroughKeyParser(win_id, 'prompt', modeman,
                                                  warn=False),
        KM.yesno: modeparsers.PromptKeyParser(win_id, modeman),
    }
    objreg.register('keyparsers', keyparsers, scope='window', window=win_id)
    modeman.destroyed.connect(
        functools.partial(objreg.delete, 'keyparsers', scope='window',
                          window=win_id))
    modeman.register(KM.normal, keyparsers[KM.normal].handle)
    modeman.register(KM.hint, keyparsers[KM.hint].handle)
    modeman.register(KM.insert, keyparsers[KM.insert].handle, passthrough=True)
    modeman.register(KM.passthrough, keyparsers[KM.passthrough].handle,
                     passthrough=True)
    modeman.register(KM.command, keyparsers[KM.command].handle,
                     passthrough=True)
    modeman.register(KM.prompt, keyparsers[KM.prompt].handle, passthrough=True)
    modeman.register(KM.yesno, keyparsers[KM.yesno].handle)
    return modeman


def _get_modeman(win_id):
    """Get a modemanager object."""
    return objreg.get('mode-manager', scope='window', window=win_id)


def enter(win_id, mode, reason=None, only_if_normal=False):
    """Enter the mode 'mode'."""
    _get_modeman(win_id).enter(mode, reason, only_if_normal)


def leave(win_id, mode, reason=None):
    """Leave the mode 'mode'."""
    _get_modeman(win_id).leave(mode, reason)


def maybe_leave(win_id, mode, reason=None):
    """Convenience method to leave 'mode' without exceptions."""
    try:
        _get_modeman(win_id).leave(mode, reason)
    except NotInModeError as e:
        # This is rather likely to happen, so we only log to debug log.
        log.modes.debug("{} (leave reason: {})".format(e, reason))


class EventFilter(QObject):

    """Event filter which passes the event to the corrent ModeManager."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._activated = True

    def eventFilter(self, obj, event):
        """Forward events to the correct modeman."""
        if not self._activated:
            return False
        try:
            modeman = objreg.get('mode-manager', scope='window',
                                 window='current')
            return modeman.eventFilter(obj, event)
        except objreg.RegistryUnavailableError:
            # No window available yet, or not a MainWindow
            return False
        except:
            # If there is an exception in here and we leave the eventfilter
            # activated, we'll get an infinite loop and a stack overflow.
            self._activated = False
            raise


class ModeManager(QObject):

    """Manager for keyboard modes.

    Attributes:
        passthrough: A list of modes in which to pass through events.
        mode: The mode we're currently in.
        _win_id: The window ID of this ModeManager
        _handlers: A dictionary of modes and their handlers.
        _forward_unbound_keys: If we should forward unbound keys.
        _releaseevents_to_pass: A list of keys where the keyPressEvent was
                                passed through, so the release event should as
                                well.

    Signals:
        entered: Emitted when a mode is entered.
                 arg1: The mode which has been entered.
                 arg2: The window ID of this mode manager.
        left:  Emitted when a mode is left.
                 arg1: The mode which has been left.
                 arg2: The new current mode.
                 arg3: The window ID of this mode manager.
    """

    entered = pyqtSignal(usertypes.KeyMode, int)
    left = pyqtSignal(usertypes.KeyMode, usertypes.KeyMode, int)

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self._win_id = win_id
        self._handlers = {}
        self.passthrough = []
        self.mode = usertypes.KeyMode.normal
        self._releaseevents_to_pass = []
        self._forward_unbound_keys = config.get(
            'input', 'forward-unbound-keys')
        objreg.get('config').changed.connect(self.set_forward_unbound_keys)

    def __repr__(self):
        return utils.get_repr(self, mode=self.mode,
                              passthrough=self.passthrough)

    def _eventFilter_keypress(self, event):
        """Handle filtering of KeyPress events.

        Args:
            event: The KeyPress to examine.

        Return:
            True if event should be filtered, False otherwise.
        """
        curmode = self.mode
        handler = self._handlers[curmode]
        if curmode != usertypes.KeyMode.insert:
            log.modes.debug("got keypress in mode {} - calling handler "
                            "{}".format(curmode, utils.qualname(handler)))
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
                            "{} (focused: {!r})".format(
                                handled, self._forward_unbound_keys,
                                curmode in self.passthrough,
                                is_non_alnum, filter_this,
                                QApplication.instance().focusWidget()))
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
        if self.mode != usertypes.KeyMode.insert:
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

    def enter(self, mode, reason=None, only_if_normal=False):
        """Enter a new mode.

        Args:
            mode: The mode to enter as a KeyMode member.
            reason: Why the mode was entered.
            only_if_normal: Only enter the new mode if we're in normal mode.
        """
        if not isinstance(mode, usertypes.KeyMode):
            raise TypeError("Mode {} is no KeyMode member!".format(mode))
        log.modes.debug("Entering mode {}{}".format(
            mode, '' if reason is None else ' (reason: {})'.format(reason)))
        if mode not in self._handlers:
            raise ValueError("No handler for mode {}".format(mode))
        prompt_modes = (usertypes.KeyMode.prompt, usertypes.KeyMode.yesno)
        if self.mode == mode or (self.mode in prompt_modes and
                                 mode in prompt_modes):
            log.modes.debug("Ignoring request as we're in mode {} "
                            "already.".format(self.mode))
            return
        if self.mode != usertypes.KeyMode.normal:
            if only_if_normal:
                log.modes.debug("Ignoring request as we're in mode {} "
                                "and only_if_normal is set..".format(
                                    self.mode))
                return
            log.modes.debug("Overriding mode {}.".format(self.mode))
            self.left.emit(self.mode, mode, self._win_id)
        self.mode = mode
        self.entered.emit(mode, self._win_id)

    @cmdutils.register(instance='mode-manager', hide=True, scope='window')
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
        """
        if self.mode != mode:
            raise NotInModeError("Not in mode {}!".format(mode))
        log.modes.debug("Leaving mode {}{}".format(
            mode, '' if reason is None else ' (reason: {})'.format(reason)))
        self.mode = usertypes.KeyMode.normal
        self.left.emit(mode, self.mode, self._win_id)

    @cmdutils.register(instance='mode-manager', name='leave-mode',
                       not_modes=[usertypes.KeyMode.normal], hide=True,
                       scope='window')
    def leave_current_mode(self):
        """Leave the mode we're currently in."""
        if self.mode == usertypes.KeyMode.normal:
            raise ValueError("Can't leave normal mode!")
        self.leave(self.mode, 'leave current')

    @config.change_filter('input', 'forward-unbound-keys')
    def set_forward_unbound_keys(self):
        """Update local setting when config changed."""
        self._forward_unbound_keys = config.get(
            'input', 'forward-unbound-keys')

    def eventFilter(self, obj, event):
        """Filter all events based on the currently set mode.

        Also calls the real keypress handler.

        Args:
            event: The KeyPress to examine.

        Return:
            True if event should be filtered, False otherwise.
        """
        if self.mode is None:
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
        if (QApplication.instance().activeWindow() not in
                objreg.window_registry.values()):
            # Some other window (print dialog, etc.) is focused so we pass
            # the event through.
            return False

        if typ == QEvent.KeyPress:
            return self._eventFilter_keypress(event)
        else:
            return self._eventFilter_keyrelease(event)
