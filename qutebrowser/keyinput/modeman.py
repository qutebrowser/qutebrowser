# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Mode manager singleton which handles the current keyboard mode."""

import functools

from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QObject, QEvent
from PyQt5.QtWidgets import QApplication

from qutebrowser.keyinput import modeparsers, keyparser
from qutebrowser.config import config
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.utils import usertypes, log, objreg, utils


class KeyEvent:

    """A small wrapper over a QKeyEvent storing its data.

    This is needed because Qt apparently mutates existing events with new data.
    It doesn't store the modifiers because they can be different for a key
    press/release.

    Attributes:
        key: A Qt.Key member (QKeyEvent::key).
        text: A string (QKeyEvent::text).
    """

    def __init__(self, keyevent):
        self.key = keyevent.key()
        self.text = keyevent.text()

    def __repr__(self):
        return utils.get_repr(self, key=self.key, text=self.text)

    def __eq__(self, other):
        return self.key == other.key and self.text == other.text

    def __hash__(self):
        return hash((self.key, self.text))


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
        KM.caret: modeparsers.CaretKeyParser(win_id, modeman),
        KM.set_mark: modeparsers.RegisterKeyParser(win_id, KM.set_mark,
                                                   modeman),
        KM.jump_mark: modeparsers.RegisterKeyParser(win_id, KM.jump_mark,
                                                    modeman),
        KM.record_macro: modeparsers.RegisterKeyParser(win_id, KM.record_macro,
                                                       modeman),
        KM.run_macro: modeparsers.RegisterKeyParser(win_id, KM.run_macro,
                                                    modeman),
    }
    objreg.register('keyparsers', keyparsers, scope='window', window=win_id)
    modeman.destroyed.connect(
        functools.partial(objreg.delete, 'keyparsers', scope='window',
                          window=win_id))
    for mode, parser in keyparsers.items():
        modeman.register(mode, parser)
    return modeman


def instance(win_id):
    """Get a modemanager object."""
    return objreg.get('mode-manager', scope='window', window=win_id)


def enter(win_id, mode, reason=None, only_if_normal=False):
    """Enter the mode 'mode'."""
    instance(win_id).enter(mode, reason, only_if_normal)


def leave(win_id, mode, reason=None, *, maybe=False):
    """Leave the mode 'mode'."""
    instance(win_id).leave(mode, reason, maybe=maybe)


class ModeManager(QObject):

    """Manager for keyboard modes.

    Attributes:
        mode: The mode we're currently in.
        _win_id: The window ID of this ModeManager
        _parsers: A dictionary of modes and their keyparsers.
        _forward_unbound_keys: If we should forward unbound keys.
        _releaseevents_to_pass: A set of KeyEvents where the keyPressEvent was
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
        self._parsers = {}
        self.mode = usertypes.KeyMode.normal
        self._releaseevents_to_pass = set()
        self._forward_unbound_keys = config.get(
            'input', 'forward-unbound-keys')
        objreg.get('config').changed.connect(self.set_forward_unbound_keys)

    def __repr__(self):
        return utils.get_repr(self, mode=self.mode)

    def _eventFilter_keypress(self, event):
        """Handle filtering of KeyPress events.

        Args:
            event: The KeyPress to examine.

        Return:
            True if event should be filtered, False otherwise.
        """
        curmode = self.mode
        parser = self._parsers[curmode]
        if curmode != usertypes.KeyMode.insert:
            log.modes.debug("got keypress in mode {} - delegating to "
                            "{}".format(curmode, utils.qualname(parser)))
        handled = parser.handle(event)

        is_non_alnum = (
            event.modifiers() not in [Qt.NoModifier, Qt.ShiftModifier] or
            not event.text().strip())

        if handled:
            filter_this = True
        elif (parser.passthrough or self._forward_unbound_keys == 'all' or
              (self._forward_unbound_keys == 'auto' and is_non_alnum)):
            filter_this = False
        else:
            filter_this = True

        if not filter_this:
            self._releaseevents_to_pass.add(KeyEvent(event))

        if curmode != usertypes.KeyMode.insert:
            focus_widget = QApplication.instance().focusWidget()
            log.modes.debug("handled: {}, forward-unbound-keys: {}, "
                            "passthrough: {}, is_non_alnum: {} --> "
                            "filter: {} (focused: {!r})".format(
                                handled, self._forward_unbound_keys,
                                parser.passthrough, is_non_alnum, filter_this,
                                focus_widget))
        return filter_this

    def _eventFilter_keyrelease(self, event):
        """Handle filtering of KeyRelease events.

        Args:
            event: The KeyPress to examine.

        Return:
            True if event should be filtered, False otherwise.
        """
        # handle like matching KeyPress
        keyevent = KeyEvent(event)
        if keyevent in self._releaseevents_to_pass:
            self._releaseevents_to_pass.remove(keyevent)
            filter_this = False
        else:
            filter_this = True
        if self.mode != usertypes.KeyMode.insert:
            log.modes.debug("filter: {}".format(filter_this))
        return filter_this

    def register(self, mode, parser):
        """Register a new mode.

        Args:
            mode: The name of the mode.
            parser: The KeyParser which should be used.
        """
        assert isinstance(mode, usertypes.KeyMode)
        assert parser is not None
        self._parsers[mode] = parser
        parser.request_leave.connect(self.leave)

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
        if mode not in self._parsers:
            raise ValueError("No keyparser for mode {}".format(mode))
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

    @pyqtSlot(usertypes.KeyMode, str, bool)
    def leave(self, mode, reason=None, maybe=False):
        """Leave a key mode.

        Args:
            mode: The mode to leave as a usertypes.KeyMode member.
            reason: Why the mode was left.
            maybe: If set, ignore the request if we're not in that mode.
        """
        if self.mode != mode:
            if maybe:
                log.modes.debug("Ignoring leave request for {} (reason {}) as "
                                "we're in mode {}".format(
                                    mode, reason, self.mode))
                return
            else:
                raise NotInModeError("Not in mode {}!".format(mode))

        log.modes.debug("Leaving mode {}{}".format(
            mode, '' if reason is None else ' (reason: {})'.format(reason)))
        # leaving a mode implies clearing keychain, see
        # https://github.com/The-Compiler/qutebrowser/issues/1805
        self.clear_keychain()
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

    def eventFilter(self, event):
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
        if event.type() == QEvent.KeyPress:
            return self._eventFilter_keypress(event)
        else:
            return self._eventFilter_keyrelease(event)

    @cmdutils.register(instance='mode-manager', scope='window', hide=True)
    def clear_keychain(self):
        """Clear the currently entered key chain."""
        self._parsers[self.mode].clear_keystring()
