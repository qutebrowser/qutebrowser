# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Base class for vim-like key sequence parser."""

import string
import types
import dataclasses
import traceback
from typing import Mapping, MutableMapping, Optional, Sequence, List

from qutebrowser.qt.core import QObject, pyqtSignal
from qutebrowser.qt.gui import QKeySequence, QKeyEvent

from qutebrowser.config import config
from qutebrowser.utils import log, usertypes, utils, message
from qutebrowser.keyinput import keyutils


@dataclasses.dataclass(frozen=True)
class MatchResult:

    """The result of matching a keybinding."""

    match_type: QKeySequence.SequenceMatch
    command: Optional[str]
    sequence: keyutils.KeySequence

    def __post_init__(self) -> None:
        if self.match_type == QKeySequence.SequenceMatch.ExactMatch:
            assert self.command is not None
        else:
            assert self.command is None


class BindingTrie:

    """Helper class for key parser. Represents a set of bindings.

    Every BindingTree will either contain children or a command (for leaf
    nodes). The only exception is the root BindingNode, if there are no
    bindings at all.

    From the outside, this class works similar to a mapping of
    keyutils.KeySequence to str. Doing trie[sequence] = 'command' adds a
    binding, and so does calling .update() with a mapping. Additionally, a
    "matches" method can be used to do partial matching.

    However, some mapping methods are not (yet) implemented:
    - __getitem__ (use matches() instead)
    - __len__
    - __iter__
    - __delitem__

    Attributes:
        children: A mapping from KeyInfo to children BindingTries.
        command: Command associated with this trie node.
    """

    __slots__ = 'children', 'command'

    def __init__(self) -> None:
        self.children: MutableMapping[keyutils.KeyInfo, BindingTrie] = {}
        self.command: Optional[str] = None

    def __setitem__(self, sequence: keyutils.KeySequence,
                    command: str) -> None:
        node = self
        for key in sequence:
            if key not in node.children:
                node.children[key] = BindingTrie()
            node = node.children[key]

        node.command = command

    def __contains__(self, sequence: keyutils.KeySequence) -> bool:
        return self.matches(sequence).match_type == QKeySequence.SequenceMatch.ExactMatch

    def __repr__(self) -> str:
        return utils.get_repr(self, children=self.children,
                              command=self.command)

    def __str__(self) -> str:
        return '\n'.join(self.string_lines(blank=True))

    def string_lines(self, indent: int = 0, blank: bool = False) -> Sequence[str]:
        """Get a list of strings for a pretty-printed version of this trie."""
        lines = []
        if self.command is not None:
            lines.append('{}=> {}'.format('  ' * indent, self.command))

        for key, child in sorted(self.children.items()):
            lines.append('{}{}:'.format('  ' * indent, key))
            lines.extend(child.string_lines(indent=indent+1))
            if blank:
                lines.append('')

        return lines

    def update(self, mapping: Mapping[keyutils.KeySequence, str]) -> None:
        """Add data from the given mapping to the trie."""
        for key in mapping:
            self[key] = mapping[key]

    def matches(self, sequence: keyutils.KeySequence) -> MatchResult:
        """Try to match a given keystring with any bound keychain.

        Args:
            sequence: The key sequence to match.

        Return:
            A MatchResult object.
        """
        node = self
        for key in sequence:
            try:
                node = node.children[key]
            except KeyError:
                return MatchResult(match_type=QKeySequence.SequenceMatch.NoMatch,
                                   command=None,
                                   sequence=sequence)

        if node.command is not None:
            return MatchResult(match_type=QKeySequence.SequenceMatch.ExactMatch,
                               command=node.command,
                               sequence=sequence)
        elif node.children:
            return MatchResult(match_type=QKeySequence.SequenceMatch.PartialMatch,
                               command=None,
                               sequence=sequence)
        else:  # This can only happen when there are no bindings at all.
            return MatchResult(match_type=QKeySequence.SequenceMatch.NoMatch,
                               command=None,
                               sequence=sequence)


class BaseKeyParser(QObject):

    """Parser for vim-like key sequences and shortcuts.

    Not intended to be instantiated directly. Subclasses have to override
    execute() to do whatever they want to.

    Attributes:
        mode_name: The name of the mode in the config.
        bindings: Bound key bindings
        _mode: The usertypes.KeyMode associated with this keyparser.
        _win_id: The window ID this keyparser is associated with.
        _pure_sequence: The currently entered key sequence (exactly as typed,
                        no substitutions performed)
        _sequence: The currently entered key sequence
        _count: The currently entered count
        _count_keyposs: Locations of count characters in the typed sequence
                        (self._count[i] was typed before
                        self._pure_sequence[self._count_keyposs[i]])
        _do_log: Whether to log keypresses or not.
        passthrough: Whether unbound keys should be passed through with this
                     handler.
        _supports_count: Whether count is supported.
        allow_partial_timeout: Whether this key parser allows for partial keys
                               to be forwarded after a timeout.
        allow_forward: Whether this key parser allows for unmatched partial
                       keys to be forwarded to underlying widgets.
        forward_widget_name: Name of the widget to which partial keys are
                             forwarded. If None, the browser's current widget
                             is used.

    Signals:
        keystring_updated: Emitted when the keystring is updated.
                           arg: New keystring.
        request_leave: Emitted to request leaving a mode.
                       arg 0: Mode to leave.
                       arg 1: Reason for leaving.
                       arg 2: Ignore the request if we're not in that mode
        forward_partial_key: Emitted when a partial key should be forwarded.
                             arg: Text expected to be forwarded (used solely
                                  for debug info, default is None).
        clear_partial_keys: Emitted to clear recorded partial keys.
    """

    keystring_updated = pyqtSignal(str)
    request_leave = pyqtSignal(usertypes.KeyMode, str, bool)
    forward_partial_key = pyqtSignal(str)
    clear_partial_keys = pyqtSignal()

    def __init__(self, *, mode: usertypes.KeyMode,
                 win_id: int,
                 parent: QObject = None,
                 do_log: bool = True,
                 passthrough: bool = False,
                 supports_count: bool = True,
                 allow_partial_timeout: bool = False,
                 allow_forward: bool = True) -> None:
        super().__init__(parent)
        self._win_id = win_id
        self._pure_sequence = keyutils.KeySequence()
        self._sequence = keyutils.KeySequence()
        self._count = ''
        self._count_keyposs: List[int] = []
        self._mode = mode
        self._do_log = do_log
        self.passthrough = passthrough
        self._supports_count = supports_count
        self.allow_partial_timeout = allow_partial_timeout
        self.allow_forward = allow_forward
        self.forward_widget_name = None
        self.bindings = BindingTrie()
        self._read_config()
        config.instance.changed.connect(self._on_config_changed)

    def __repr__(self) -> str:
        return utils.get_repr(self, mode=self._mode,
                              win_id=self._win_id,
                              do_log=self._do_log,
                              passthrough=self.passthrough,
                              supports_count=self._supports_count,
                              allow_partial_timeout=self.allow_partial_timeout)

    def _debug_log(self, msg: str) -> None:
        """Log a message to the debug log if logging is active.

        Args:
            message: The message to log.
        """
        if self._do_log:
            prefix = '{} for mode {}: '.format(self.__class__.__name__,
                                               self._mode.name)
            log.keyboard.debug(prefix + msg)

    def set_forward_widget_name(self,
                                forward_widget_name: str) -> 'BaseKeyParser':
        """Set forward_widget_name.

        Args:
            forward_widget_name: Name of the widget to which partial keys are
                                 forwarded.
        """
        self.forward_widget_name = forward_widget_name
        return self

    def get_do_log(self) -> bool:
        return self._do_log

    def _match_key(self, sequence: keyutils.KeySequence) -> MatchResult:
        """Try to match a given keystring with any bound keychain.

        Args:
            sequence: The command string to find.

        Return:
            A tuple (matchtype, binding).
                matchtype: Match.definitive, Match.partial or Match.none.
                binding: - None with Match.partial/Match.none.
                         - The found binding with Match.definitive.
        """
        assert sequence
        return self.bindings.matches(sequence)

    def _match_without_modifiers(
            self, sequence: keyutils.KeySequence) -> MatchResult:
        """Try to match a key with optional modifiers stripped."""
        self._debug_log("Trying match without modifiers")
        sequence = sequence.strip_modifiers()
        return self._match_key(sequence)

    def _match_key_mapping(
            self, sequence: keyutils.KeySequence) -> MatchResult:
        """Try to match a key in bindings.key_mappings."""
        self._debug_log("Trying match with key_mappings")
        mapped = sequence.with_mappings(
            types.MappingProxyType(config.cache['bindings.key_mappings']))
        if sequence != mapped:
            self._debug_log("Mapped {} -> {}".format(
                sequence, mapped))
            return self._match_key(mapped)
        return MatchResult(match_type=QKeySequence.SequenceMatch.NoMatch,
                           command=None,
                           sequence=sequence)

    def _match_count(self, sequence: keyutils.KeySequence, count: str,
                     keypos: int, dry_run: bool) -> bool:
        """Try to match a key as count."""
        if not config.val.input.match_counts:
            return False

        txt = str(sequence[-1])  # To account for sequences changed above.
        if (txt in string.digits and self._supports_count and
                not (not count and txt == '0')):
            self._debug_log("Trying match as count")
            assert len(txt) == 1, txt
            if not dry_run:
                self._count += txt
                self._count_keyposs.append(keypos)
                self.keystring_updated.emit(self._count + str(self._sequence))
            return True
        return False

    def handle(self, e: QKeyEvent, *,  # noqa: C901
               dry_run: bool = False) -> QKeySequence.SequenceMatch:
        """Handle a new keypress.

        Separate the keypress into count/command, then check if it matches
        any possible command, and either run the command, ignore it, or
        display an error.

        Args:
            e: the KeyPressEvent from Qt.
            dry_run: Don't actually execute anything, only check whether there
                     would be a match.

        Return:
            A QKeySequence match.
        """
        try:
            info = keyutils.KeyInfo.from_event(e)
        except keyutils.InvalidKeyError as ex:
            # See https://github.com/qutebrowser/qutebrowser/issues/7047
            log.keyboard.debug(f"Got invalid key: {ex}")
            self.clear_keystring()
            return QKeySequence.SequenceMatch.NoMatch

        self._debug_log(f"Got key: {info!r} (dry_run {dry_run})")

        # Modifier keys should be previously handled by modeman
        if info.is_modifier_key():
            self._debug_log("Ignoring, only modifier")
            return QKeySequence.SequenceMatch.NoMatch

        had_empty_queue = (not self._pure_sequence) and (not self._count)

        try:
            pure_sequence = self._pure_sequence.append_event(e)
        except keyutils.KeyParseError as ex:
            self._debug_log("{} Aborting keychain.".format(ex))
            self.clear_keystring()
            return QKeySequence.SequenceMatch.NoMatch

        flag0 = True
        # Have these shadow variables to have replicable behavior when doing a
        # dry run
        count = self._count
        count_keyposs = self._count_keyposs.copy()
        while pure_sequence:
            result = self._match_key(pure_sequence)
            # Enforce code below to use the modified result.sequence
            if result.match_type == QKeySequence.SequenceMatch.NoMatch:
                self._debug_log("No match for '{}'. Attempting without "
                                "modifiers.".format(result.sequence))
                result = self._match_without_modifiers(result.sequence)
            if result.match_type == QKeySequence.SequenceMatch.NoMatch:
                self._debug_log("No match for '{}'. Attempting with key "
                                "mappings.".format(result.sequence))
                seq_len = len(result.sequence)
                result = self._match_key_mapping(result.sequence)
            if (result.match_type == QKeySequence.SequenceMatch.NoMatch) and flag0:
                flag0 = False
                # this length check is to ensure that key mappings from the
                # _match_key_mapping call that directly convert a single key to
                # a numeral character are allowed to be recognized as counts.
                # The case where a mapping from a single key to multiple keys
                # (including a count) is present is unlikely, and the handling
                # of such an event is not obvious, so for now we do not support
                # it at all.
                if len(result.sequence) == seq_len:
                    self._debug_log("No match for '{}'. Attempting count "
                                    "match.".format(result.sequence))
                    was_count = self._match_count(result.sequence, count,
                        len(self._pure_sequence), dry_run)
                    if was_count:
                        self._debug_log("Was a count match.")
                        return QKeySequence.SequenceMatch.PartialMatch
                else:
                    self._debug_log("No match for '{}'. Mappings expanded "
                                    "the length of the sequence, so no count "
                                    "matching will be attempted.".format(
                                        result.sequence))
            if not dry_run:
                # Update state variables
                self._sequence = result.sequence
                self._pure_sequence = pure_sequence
            if result.match_type != QKeySequence.SequenceMatch.NoMatch:
                break
            assert pure_sequence
            if not had_empty_queue:
                self._debug_log("No match for '{}'. Will forward first "
                                "key in the sequence and retry.".format(
                                    result.sequence))
                # Forward all the leading count keys
                while count_keyposs and (count_keyposs[0] == 0):
                    self._debug_log("Hit a queued count key ('{}'). "
                                    "Forwarding.".format(count[0]))
                    count = count[1:]
                    count_keyposs.pop(0)
                    if not dry_run:
                        self.forward_partial_key.emit(self._count[0])
                        self._count = self._count[1:]
                        self._count_keyposs.pop(0)
                self._debug_log("Forwarding first key in sequence "
                                "('{}').".format(str(pure_sequence[0])))
                # Update the count_keyposs to reflect the shortened
                # pure_sequence
                count_keyposs = [x - 1 for x in count_keyposs]
                if not dry_run:
                    self._count_keyposs = [x - 1 for x in self._count_keyposs]
                    self.forward_partial_key.emit(str(self._pure_sequence[0]))
            else:
                self._debug_log("No partial keys in queue. Continuing.")
            pure_sequence = pure_sequence[1:]
            # self._pure_sequence is updated either on next loop in the 'Update
            # state variables' block or (if pure_sequence is empty and there is
            # no next loop) in the self.clear_keystring call in the NoMatch
            # block below

        if dry_run:
            return result.match_type
        self._handle_result(info, result)
        return result.match_type

    def _handle_result(self, info: keyutils.KeyInfo, result: MatchResult) -> None:
        """Handle a final MatchResult from handle()."""
        # Each of the three following blocks need to emit
        # self.keystring_updated, either directly (as PartialMatch does) or
        # indirectly (as ExactMatch and NoMatch do via self.clear_keystring)
        if result.match_type == QKeySequence.SequenceMatch.ExactMatch:
            assert result.command is not None
            self._debug_log("Definitive match for '{}'.".format(
                result.sequence))
            try:
                # note: this 'count' is an int, not a str
                count = int(self._count) if self._count else None
                flag_do_execute = True
            except ValueError as err:
                message.error(f"Failed to parse count: {err}",
                              stack=traceback.format_exc())
                flag_do_execute = False
            self.clear_partial_keys.emit()
            self.clear_keystring()
            if flag_do_execute:
                self.execute(result.command, count)
        elif result.match_type == QKeySequence.SequenceMatch.PartialMatch:
            self._debug_log("No match for '{}' (added {})".format(
                result.sequence, info))
            self.keystring_updated.emit(self._count + str(result.sequence))
        elif result.match_type == QKeySequence.SequenceMatch.NoMatch:
            self._debug_log("Giving up with '{}', no matches".format(
                result.sequence))
            self.clear_keystring()
        else:
            raise utils.Unreachable("Invalid match value {!r}".format(
                result.match_type))

    @config.change_filter('bindings')
    def _on_config_changed(self) -> None:
        self._read_config()

    def _read_config(self) -> None:
        """Read the configuration."""
        self.bindings = BindingTrie()
        config_bindings = config.key_instance.get_bindings_for(self._mode.name)

        for key, cmd in config_bindings.items():
            assert cmd
            self.bindings[key] = cmd

    def execute(self, cmdstr: str, count: int = None) -> None:
        """Handle a completed keychain.

        Args:
            cmdstr: The command to execute as a string.
            count: The count if given.
        """
        raise NotImplementedError

    def clear_keystring(self) -> None:
        """Clear the currently entered key sequence."""
        do_emit = False
        if self._count:
            do_emit = True
            self._debug_log("Clearing keystring count (was: {}).".format(
                self._count))
            self._count = ''
            self._count_keyposs = []
        # self._pure_sequence should non-empty if and only if self._sequence is
        # non-empty, but to be safe both conditions are included below
        if self._pure_sequence or self._sequence:
            do_emit = True
            self._debug_log("Clearing keystring (was: {}).".format(
                self._sequence))
            self._pure_sequence = keyutils.KeySequence()
            self._sequence = keyutils.KeySequence()
        if do_emit:
            self.keystring_updated.emit('')
