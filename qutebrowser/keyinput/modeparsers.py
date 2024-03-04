# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""KeyChainParser for "hint" and "normal" modes.

Module attributes:
    STARTCHARS: Possible chars for starting a commandline input.
"""

import traceback
import enum
import functools
from typing import TYPE_CHECKING, Sequence, List

from qutebrowser.qt.core import pyqtSlot, Qt, QObject
from qutebrowser.qt.gui import QKeySequence, QKeyEvent

from qutebrowser.browser import hints
from qutebrowser.commands import cmdexc
from qutebrowser.config import config
from qutebrowser.keyinput import basekeyparser, keyutils, macros
from qutebrowser.utils import usertypes, log, message, objreg, utils
if TYPE_CHECKING:
    from qutebrowser.commands import runners


STARTCHARS = ":/?"


class LastPress(enum.Enum):

    """Whether the last keypress filtered a text or was part of a keystring."""

    none = enum.auto()
    filtertext = enum.auto()
    keystring = enum.auto()


class CommandKeyParser(basekeyparser.BaseKeyParser):

    """KeyChainParser for command bindings.

    Attributes:
        _commandrunner: CommandRunner instance.
    """

    def __init__(self, *, mode: usertypes.KeyMode,
                 win_id: int,
                 commandrunner: 'runners.CommandRunner',
                 parent: QObject = None,
                 do_log: bool = True,
                 passthrough: bool = False,
                 supports_count: bool = True,
                 allow_partial_timeout: bool = True,
                 allow_forward: bool = True) -> None:
        super().__init__(mode=mode, win_id=win_id, parent=parent,
                         do_log=do_log, passthrough=passthrough,
                         supports_count=supports_count,
                         allow_partial_timeout=allow_partial_timeout,
                         allow_forward=allow_forward)
        self._commandrunner = commandrunner

    def execute(self, cmdstr: str, count: int = None) -> None:
        try:
            self._commandrunner.run(cmdstr, count)
        except cmdexc.Error as e:
            message.error(str(e), stack=traceback.format_exc())


class NormalKeyParser(CommandKeyParser):

    """KeyParser for normal mode with added STARTCHARS detection and more."""

    _sequence: keyutils.KeySequence

    def __init__(self, *, win_id: int,
                 commandrunner: 'runners.CommandRunner',
                 parent: QObject = None) -> None:
        super().__init__(mode=usertypes.KeyMode.normal, win_id=win_id,
                         commandrunner=commandrunner, parent=parent)
        self._inhibited = False
        self._inhibited_timer = usertypes.Timer(self, 'normal-inhibited')
        self._inhibited_timer.setSingleShot(True)
        self._inhibited_timer.timeout.connect(self._clear_inhibited)

    def __repr__(self) -> str:
        return utils.get_repr(self)

    def handle(self, e: QKeyEvent, *,
               dry_run: bool = False) -> QKeySequence.SequenceMatch:
        """Override to abort if the key is a startchar."""
        txt = e.text().strip()
        if self._inhibited:
            self._debug_log("Ignoring key '{}', because the normal mode is "
                            "currently inhibited.".format(txt))
            return QKeySequence.SequenceMatch.NoMatch

        return super().handle(e, dry_run=dry_run)

    def set_inhibited_timeout(self, timeout: int) -> None:
        """Ignore keypresses for the given duration."""
        if timeout != 0:
            self._debug_log("Inhibiting the normal mode for {}ms.".format(
                timeout))
            self._inhibited = True
            self._inhibited_timer.setInterval(timeout)
            self._inhibited_timer.start()

    @pyqtSlot()
    def _clear_inhibited(self) -> None:
        """Reset inhibition state after a timeout."""
        self._debug_log("Releasing inhibition state of normal mode.")
        self._inhibited = False


class HintKeyParser(basekeyparser.BaseKeyParser):

    """KeyChainParser for hints.

    Attributes:
        _filtertext: The text to filter with.
        _hintmanager: The HintManager to use.
        _last_press: The nature of the last keypress, a LastPress member.
        _partial_timer: The timer which forwards partial keys after no key has
                        been pressed for a timeout period.
    """

    _sequence: keyutils.KeySequence

    def __init__(self, *, win_id: int,
                 commandrunner: 'runners.CommandRunner',
                 hintmanager: hints.HintManager,
                 parent: QObject = None) -> None:
        super().__init__(mode=usertypes.KeyMode.hint, win_id=win_id,
                         parent=parent, supports_count=False,
                         allow_partial_timeout=False, allow_forward=False)
        self._command_parser = CommandKeyParser(mode=usertypes.KeyMode.hint,
                                                win_id=win_id,
                                                commandrunner=commandrunner,
                                                parent=self,
                                                supports_count=False,
                                                allow_partial_timeout=True)
        self._hintmanager = hintmanager
        self._filtertext = ''
        self._last_press = LastPress.none
        self._partial_match_events: List[keyutils.QueuedKeyEventPair] = []
        self.keystring_updated.connect(self._hintmanager.handle_partial_key)
        self._command_parser.forward_partial_key.connect(
            self.forward_partial_match_event)
        self._command_parser.clear_partial_keys.connect(
            self.clear_partial_match_events)
        self._partial_timer = usertypes.Timer(self, 'partial-match')
        self._partial_timer.setSingleShot(True)
        self._partial_timer.timeout.connect(functools.partial(
            self.forward_all_partial_match_events, is_timeout=True))

    def _handle_filter_key(self, e: QKeyEvent) -> QKeySequence.SequenceMatch:
        """Handle keys for string filtering."""
        log.keyboard.debug("Got filter key 0x{:x} text {}".format(
            e.key(), e.text()))
        if e.key() == Qt.Key.Key_Backspace:
            log.keyboard.debug("Got backspace, mode {}, filtertext '{}', "
                               "sequence '{}'".format(self._last_press,
                                                      self._filtertext,
                                                      self._sequence))
            if self._last_press != LastPress.keystring and self._filtertext:
                self._filtertext = self._filtertext[:-1]
                self._hintmanager.filter_hints(self._filtertext)
                return QKeySequence.SequenceMatch.ExactMatch
            elif self._last_press == LastPress.keystring and self._sequence:
                self._sequence = self._sequence[:-1]
                self.keystring_updated.emit(str(self._sequence))
                if not self._sequence and self._filtertext:
                    # Switch back to hint filtering mode (this can happen only
                    # in numeric mode after the number has been deleted).
                    self._hintmanager.filter_hints(self._filtertext)
                    self._last_press = LastPress.filtertext
                return QKeySequence.SequenceMatch.ExactMatch
            else:
                return QKeySequence.SequenceMatch.NoMatch
        elif self._hintmanager.current_mode() != 'number':
            return QKeySequence.SequenceMatch.NoMatch
        elif not e.text():
            return QKeySequence.SequenceMatch.NoMatch
        else:
            self._filtertext += e.text()
            self._hintmanager.filter_hints(self._filtertext)
            self._last_press = LastPress.filtertext
            return QKeySequence.SequenceMatch.ExactMatch

    def handle(self, e: QKeyEvent, *,
               dry_run: bool = False) -> QKeySequence.SequenceMatch:
        """Handle a new keypress and call the respective handlers."""
        if dry_run:
            result = self._command_parser.handle(e, dry_run=True)
            if result != QKeySequence.SequenceMatch.NoMatch:
                return result
            return super().handle(e, dry_run=True)

        assert not dry_run

        had_empty_queue = not self._partial_match_events
        if not had_empty_queue:
            # Immediately record the event so that parser.handle may forward if
            # appropriate from its logic.
            self._debug_log("Enqueuing key event due to non-empty queue: "
                            "{}".format(e))
            self._partial_match_events.append(
                keyutils.QueuedKeyEventPair.from_event_press(e))

        result = self._command_parser.handle(e)
        if result == QKeySequence.SequenceMatch.ExactMatch:
            self._debug_log("Stopping partial timer.")
            self._stop_partial_timer()
            self.clear_partial_match_events()
            log.keyboard.debug("Handling key via command parser")
            self.clear_keystring()
            return result
        elif result == QKeySequence.SequenceMatch.PartialMatch:
            log.keyboard.debug("Handling key via command parser")
            if had_empty_queue:
                # Begin recording partial match events
                self._debug_log("Enqueuing key event as first entry in an "
                                "empty queue: {}".format(e))
                self._partial_match_events.append(
                    keyutils.QueuedKeyEventPair.from_event_press(e))
            self._debug_log("Starting partial timer.")
            self._start_partial_timer()
            return result
        elif not had_empty_queue:
            self._debug_log("Stopping partial timer.")
            self._stop_partial_timer()
            # It's unclear exactly what the return here should be. The safest
            # bet seems to be PartialMatch as it won't clear the unused
            # modeman._partial_match_events buffer, which if done could lead to
            # an issue if forward_partial were called with an empty buffer. At
            # the time of writing this, the behaviors of returning
            # ExactMatch/PartialMatch are identical, practically speaking.
            return QKeySequence.SequenceMatch.PartialMatch
        else:
            return self._handle_hint(e)

    def _handle_hint(self, e: QKeyEvent) -> QKeySequence.SequenceMatch:
        match = super().handle(e)

        if match == QKeySequence.SequenceMatch.PartialMatch:
            self._last_press = LastPress.keystring
        elif match == QKeySequence.SequenceMatch.ExactMatch:
            self._last_press = LastPress.none
        elif match == QKeySequence.SequenceMatch.NoMatch:
            # We couldn't find a keychain so we check if it's a special key.
            return self._handle_filter_key(e)
        else:
            raise ValueError("Got invalid match type {}!".format(match))

        return match

    @pyqtSlot(str)
    def forward_partial_match_event(self, text: str = None) -> None:
        """Forward the oldest partial match event.

        Args:
            text: The expected text to be forwarded. Only used for debug
                  purposes. Default is None.
        """
        if not self._partial_match_events:
            self._debug_log("Attempting to forward (expected text = {}) but "
                            "there are no events to forward.".format(text))
            return
        match_event = self._partial_match_events.pop(0)
        self._debug_log("Forwarding partial match event.")
        text_actual = str(match_event.key_info_press)
        if (text is not None) and (text_actual != text):
            self._debug_log("Text mismatch (this is likely benign): '{}' != "
                            "'{}'".format(text_actual, text))
        e = match_event.to_events()
        assert len(e) == 1
        self._handle_hint(e[0])

    @pyqtSlot()
    def forward_all_partial_match_events(self, *,
                                         stop_timer: bool = False,
                                         is_timeout: bool = False) -> None:
        """Forward all partial match events.

        Args:
            stop_timer: If true, stop the partial timer as well. Default is
                        False.
            is_timeout: True if this invocation is the result of a timeout.
        """
        self._debug_log(f"Forwarding all partial matches ({is_timeout=}).")
        if stop_timer:
            self._debug_log("Stopping partial timer.")
            self._stop_partial_timer()
        if self._partial_match_events:
            while self._partial_match_events:
                self.forward_partial_match_event()
            self._command_parser.clear_keystring()

    @pyqtSlot()
    def clear_partial_match_events(self) -> None:
        self._partial_match_events = []

    def _start_partial_timer(self) -> None:
        """Set a timeout to clear a partial keystring."""
        timeout = config.val.input.partial_timeout
        if self._command_parser.allow_partial_timeout and (timeout != 0):
            self._partial_timer.setInterval(timeout)
            self._partial_timer.start()

    def _stop_partial_timer(self) -> None:
        """Prematurely stop the the partial keystring timer."""
        self._partial_timer.stop()

    def update_bindings(self, strings: Sequence[str],
                        preserve_filter: bool = False) -> None:
        """Update bindings when the hint strings changed.

        Args:
            strings: A list of hint strings.
            preserve_filter: Whether to keep the current value of
                             `self._filtertext`.
        """
        self._read_config()
        self.bindings.update({keyutils.KeySequence.parse(s): s
                              for s in strings})
        if not preserve_filter:
            self._filtertext = ''

    def execute(self, cmdstr: str, count: int = None) -> None:
        assert count is None
        self._hintmanager.handle_partial_key(cmdstr)


class RegisterKeyParser(CommandKeyParser):

    """KeyParser for modes that record a register key.

    Attributes:
        _register_mode: One of KeyMode.set_mark, KeyMode.jump_mark,
                        KeyMode.record_macro and KeyMode.run_macro.
    """

    def __init__(self, *, win_id: int,
                 mode: usertypes.KeyMode,
                 commandrunner: 'runners.CommandRunner',
                 parent: QObject = None) -> None:
        super().__init__(mode=usertypes.KeyMode.register,
                         win_id=win_id,
                         commandrunner=commandrunner,
                         parent=parent,
                         supports_count=False,
                         allow_partial_timeout=False)
        self._register_mode = mode

    def handle(self, e: QKeyEvent, *,
               dry_run: bool = False) -> QKeySequence.SequenceMatch:
        """Override to always match the next key and use the register."""
        match = super().handle(e, dry_run=dry_run)
        if match != QKeySequence.SequenceMatch.NoMatch or dry_run:
            return match

        try:
            info = keyutils.KeyInfo.from_event(e)
        except keyutils.InvalidKeyError as ex:
            # See https://github.com/qutebrowser/qutebrowser/issues/7047
            log.keyboard.debug(f"Got invalid key: {ex}")
            return QKeySequence.SequenceMatch.NoMatch
        if info.is_special():
            # this is not a proper register key, let it pass and keep going
            return QKeySequence.SequenceMatch.NoMatch

        key = e.text()

        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._win_id)

        try:
            if self._register_mode == usertypes.KeyMode.set_mark:
                tabbed_browser.set_mark(key)
            elif self._register_mode == usertypes.KeyMode.jump_mark:
                tabbed_browser.jump_mark(key)
            elif self._register_mode == usertypes.KeyMode.record_macro:
                macros.macro_recorder.record_macro(key)
            elif self._register_mode == usertypes.KeyMode.run_macro:
                macros.macro_recorder.run_macro(self._win_id, key)
            else:
                raise ValueError("{} is not a valid register mode".format(
                    self._register_mode))
        except cmdexc.Error as err:
            message.error(str(err), stack=traceback.format_exc())

        self.request_leave.emit(
            self._register_mode, "valid register key", True)
        return QKeySequence.SequenceMatch.ExactMatch
