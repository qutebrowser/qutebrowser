# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""KeyChainParser for "hint" and "normal" modes.

Module attributes:
    STARTCHARS: Possible chars for starting a commandline input.
"""

import typing
import traceback
import enum

from PyQt5.QtCore import pyqtSlot, Qt, QObject
from PyQt5.QtGui import QKeySequence, QKeyEvent

from qutebrowser.browser import hints
from qutebrowser.commands import cmdexc
from qutebrowser.config import config
from qutebrowser.keyinput import basekeyparser, keyutils, macros
from qutebrowser.utils import usertypes, log, message, objreg, utils
if typing.TYPE_CHECKING:
    from qutebrowser.commands import runners


STARTCHARS = ":/?"
LastPress = enum.Enum('LastPress', ['none', 'filtertext', 'keystring'])


class CommandKeyParser(basekeyparser.BaseKeyParser):

    """KeyChainParser for command bindings.

    Attributes:
        _commandrunner: CommandRunner instance.
    """

    def __init__(self, win_id: int,
                 commandrunner: 'runners.CommandRunner',
                 parent: QObject = None) -> None:
        super().__init__(win_id, parent)
        self._commandrunner = commandrunner

    def execute(self, cmdstr: str, count: int = None) -> None:
        try:
            self._commandrunner.run(cmdstr, count)
        except cmdexc.Error as e:
            message.error(str(e), stack=traceback.format_exc())


class NormalKeyParser(CommandKeyParser):

    """KeyParser for normal mode with added STARTCHARS detection and more.

    Attributes:
        _partial_timer: Timer to clear partial keypresses.
    """

    def __init__(self, win_id: int,
                 commandrunner: 'runners.CommandRunner',
                 parent: QObject = None) -> None:
        super().__init__(win_id, commandrunner, parent)
        self._read_config('normal')
        self._partial_timer = usertypes.Timer(self, 'partial-match')
        self._partial_timer.setSingleShot(True)
        self._partial_timer.timeout.connect(self._clear_partial_match)
        self._inhibited = False
        self._inhibited_timer = usertypes.Timer(self, 'normal-inhibited')
        self._inhibited_timer.setSingleShot(True)

    def __repr__(self) -> str:
        return utils.get_repr(self)

    def handle(self, e: QKeyEvent, *,
               dry_run: bool = False) -> QKeySequence.SequenceMatch:
        """Override to abort if the key is a startchar."""
        txt = e.text().strip()
        if self._inhibited:
            self._debug_log("Ignoring key '{}', because the normal mode is "
                            "currently inhibited.".format(txt))
            return QKeySequence.NoMatch

        match = super().handle(e, dry_run=dry_run)

        if match == QKeySequence.PartialMatch and not dry_run:
            timeout = config.val.input.partial_timeout
            if timeout != 0:
                self._partial_timer.setInterval(timeout)
                self._partial_timer.start()
        return match

    def set_inhibited_timeout(self, timeout: int) -> None:
        """Ignore keypresses for the given duration."""
        if timeout != 0:
            self._debug_log("Inhibiting the normal mode for {}ms.".format(
                timeout))
            self._inhibited = True
            self._inhibited_timer.setInterval(timeout)
            self._inhibited_timer.timeout.connect(self._clear_inhibited)
            self._inhibited_timer.start()

    @pyqtSlot()
    def _clear_partial_match(self) -> None:
        """Clear a partial keystring after a timeout."""
        self._debug_log("Clearing partial keystring {}".format(
            self._sequence))
        self._sequence = keyutils.KeySequence()
        self.keystring_updated.emit(str(self._sequence))

    @pyqtSlot()
    def _clear_inhibited(self) -> None:
        """Reset inhibition state after a timeout."""
        self._debug_log("Releasing inhibition state of normal mode.")
        self._inhibited = False


class PassthroughKeyParser(CommandKeyParser):

    """KeyChainParser which passes through normal keys.

    Used for insert/passthrough modes.

    Attributes:
        _mode: The mode this keyparser is for.
    """

    do_log = False
    passthrough = True
    supports_count = False

    def __init__(self, win_id: int,
                 mode: usertypes.KeyMode,
                 commandrunner: 'runners.CommandRunner',
                 parent: QObject = None) -> None:
        """Constructor.

        Args:
            mode: The mode this keyparser is for.
            parent: Qt parent.
            warn: Whether to warn if an ignored key was bound.
        """
        super().__init__(win_id, commandrunner, parent)
        self._read_config(mode.name)
        self._mode = mode

    def __repr__(self) -> str:
        return utils.get_repr(self, mode=self._mode)


class PromptKeyParser(CommandKeyParser):

    """KeyParser for yes/no prompts."""

    supports_count = False

    def __init__(self, win_id: int,
                 commandrunner: 'runners.CommandRunner',
                 parent: QObject = None) -> None:
        super().__init__(win_id, commandrunner, parent)
        self._read_config('yesno')

    def __repr__(self) -> str:
        return utils.get_repr(self)


class HintKeyParser(CommandKeyParser):

    """KeyChainParser for hints.

    Attributes:
        _filtertext: The text to filter with.
        _hintmanager: The HintManager to use.
        _last_press: The nature of the last keypress, a LastPress member.
    """

    supports_count = False

    def __init__(self, win_id: int,
                 commandrunner: 'runners.CommandRunner',
                 hintmanager: hints.HintManager,
                 parent: QObject = None) -> None:
        super().__init__(win_id, commandrunner, parent)
        self._hintmanager = hintmanager
        self._filtertext = ''
        self._last_press = LastPress.none
        self._read_config('hint')
        self.keystring_updated.connect(self._hintmanager.handle_partial_key)

    def _handle_filter_key(self, e: QKeyEvent) -> QKeySequence.SequenceMatch:
        """Handle keys for string filtering."""
        log.keyboard.debug("Got filter key 0x{:x} text {}".format(
            e.key(), e.text()))
        if e.key() == Qt.Key_Backspace:
            log.keyboard.debug("Got backspace, mode {}, filtertext '{}', "
                               "sequence '{}'".format(self._last_press,
                                                      self._filtertext,
                                                      self._sequence))
            if self._last_press != LastPress.keystring and self._filtertext:
                self._filtertext = self._filtertext[:-1]
                self._hintmanager.filter_hints(self._filtertext)
                return QKeySequence.ExactMatch
            elif self._last_press == LastPress.keystring and self._sequence:
                self._sequence = self._sequence[:-1]
                self.keystring_updated.emit(str(self._sequence))
                if not self._sequence and self._filtertext:
                    # Switch back to hint filtering mode (this can happen only
                    # in numeric mode after the number has been deleted).
                    self._hintmanager.filter_hints(self._filtertext)
                    self._last_press = LastPress.filtertext
                return QKeySequence.ExactMatch
            else:
                return QKeySequence.NoMatch
        elif self._hintmanager.current_mode() != 'number':
            return QKeySequence.NoMatch
        elif not e.text():
            return QKeySequence.NoMatch
        else:
            self._filtertext += e.text()
            self._hintmanager.filter_hints(self._filtertext)
            self._last_press = LastPress.filtertext
            return QKeySequence.ExactMatch

    def handle(self, e: QKeyEvent, *,
               dry_run: bool = False) -> QKeySequence.SequenceMatch:
        """Handle a new keypress and call the respective handlers."""
        if dry_run:
            return super().handle(e, dry_run=True)

        if keyutils.is_special_hint_mode(Qt.Key(e.key()), e.modifiers()):
            log.keyboard.debug("Got special key, clearing keychain")
            self.clear_keystring()

        assert not dry_run
        match = super().handle(e)

        if match == QKeySequence.PartialMatch:
            self._last_press = LastPress.keystring
        elif match == QKeySequence.ExactMatch:
            self._last_press = LastPress.none
        elif match == QKeySequence.NoMatch:
            # We couldn't find a keychain so we check if it's a special key.
            return self._handle_filter_key(e)
        else:
            raise ValueError("Got invalid match type {}!".format(match))

        return match

    def update_bindings(self, strings: typing.Sequence[str],
                        preserve_filter: bool = False) -> None:
        """Update bindings when the hint strings changed.

        Args:
            strings: A list of hint strings.
            preserve_filter: Whether to keep the current value of
                             `self._filtertext`.
        """
        self._read_config()
        self.bindings.update({keyutils.KeySequence.parse(s):
                              'follow-hint -s ' + s for s in strings})
        if not preserve_filter:
            self._filtertext = ''


class CaretKeyParser(CommandKeyParser):

    """KeyParser for caret mode."""

    passthrough = True

    def __init__(self, win_id: int,
                 commandrunner: 'runners.CommandRunner',
                 parent: QObject = None) -> None:
        super().__init__(win_id, commandrunner, parent)
        self._read_config('caret')


class RegisterKeyParser(CommandKeyParser):

    """KeyParser for modes that record a register key.

    Attributes:
        _mode: One of KeyMode.set_mark, KeyMode.jump_mark, KeyMode.record_macro
        and KeyMode.run_macro.
    """

    supports_count = False

    def __init__(self, win_id: int,
                 mode: usertypes.KeyMode,
                 commandrunner: 'runners.CommandRunner',
                 parent: QObject = None) -> None:
        super().__init__(win_id, commandrunner, parent)
        self._mode = mode
        self._read_config('register')

    def handle(self, e: QKeyEvent, *,
               dry_run: bool = False) -> QKeySequence.SequenceMatch:
        """Override to always match the next key and use the register."""
        match = super().handle(e, dry_run=dry_run)
        if match or dry_run:
            return match

        if keyutils.is_special(Qt.Key(e.key()), e.modifiers()):
            # this is not a proper register key, let it pass and keep going
            return QKeySequence.NoMatch

        key = e.text()

        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)

        try:
            if self._mode == usertypes.KeyMode.set_mark:
                tabbed_browser.set_mark(key)
            elif self._mode == usertypes.KeyMode.jump_mark:
                tabbed_browser.jump_mark(key)
            elif self._mode == usertypes.KeyMode.record_macro:
                macros.macro_recorder.record_macro(key)
            elif self._mode == usertypes.KeyMode.run_macro:
                macros.macro_recorder.run_macro(self._win_id, key)
            else:
                raise ValueError(
                    "{} is not a valid register mode".format(self._mode))
        except cmdexc.Error as err:
            message.error(str(err), stack=traceback.format_exc())

        self.request_leave.emit(self._mode, "valid register key", True)
        return QKeySequence.ExactMatch
