# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Base class for vim-like key sequence parser."""

import string
import types
import dataclasses
from typing import Mapping, MutableMapping, Optional, Sequence

from PyQt5.QtCore import pyqtSignal, QObject, Qt
from PyQt5.QtGui import QKeySequence, QKeyEvent

from qutebrowser.config import config
from qutebrowser.utils import usertypes, log, utils
from qutebrowser.keyinput import keyutils


@dataclasses.dataclass(frozen=True)
class MatchResult:

    """The result of matching a keybinding."""

    match_type: QKeySequence.SequenceMatch
    command: Optional[str]
    sequence: keyutils.KeySequence

    def __post_init__(self) -> None:
        if self.match_type == QKeySequence.ExactMatch:
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
        return self.matches(sequence).match_type == QKeySequence.ExactMatch

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

    def update(self, mapping: Mapping) -> None:
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
                return MatchResult(match_type=QKeySequence.NoMatch,
                                   command=None,
                                   sequence=sequence)

        if node.command is not None:
            return MatchResult(match_type=QKeySequence.ExactMatch,
                               command=node.command,
                               sequence=sequence)
        elif node.children:
            return MatchResult(match_type=QKeySequence.PartialMatch,
                               command=None,
                               sequence=sequence)
        else:  # This can only happen when there are no bindings at all.
            return MatchResult(match_type=QKeySequence.NoMatch,
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
        _sequence: The currently entered key sequence
        _do_log: Whether to log keypresses or not.
        passthrough: Whether unbound keys should be passed through with this
                     handler.
        _supports_count: Whether count is supported.

    Signals:
        keystring_updated: Emitted when the keystring is updated.
                           arg: New keystring.
        request_leave: Emitted to request leaving a mode.
                       arg 0: Mode to leave.
                       arg 1: Reason for leaving.
                       arg 2: Ignore the request if we're not in that mode
    """

    keystring_updated = pyqtSignal(str)
    request_leave = pyqtSignal(usertypes.KeyMode, str, bool)

    def __init__(self, *, mode: usertypes.KeyMode,
                 win_id: int,
                 parent: QObject = None,
                 do_log: bool = True,
                 passthrough: bool = False,
                 supports_count: bool = True) -> None:
        super().__init__(parent)
        self._win_id = win_id
        self._sequence = keyutils.KeySequence()
        self._count = ''
        self._mode = mode
        self._do_log = do_log
        self.passthrough = passthrough
        self._supports_count = supports_count
        self.bindings = BindingTrie()
        self._read_config()
        config.instance.changed.connect(self._on_config_changed)

    def __repr__(self) -> str:
        return utils.get_repr(self, mode=self._mode,
                              win_id=self._win_id,
                              do_log=self._do_log,
                              passthrough=self.passthrough,
                              supports_count=self._supports_count)

    def _debug_log(self, message: str) -> None:
        """Log a message to the debug log if logging is active.

        Args:
            message: The message to log.
        """
        if self._do_log:
            prefix = '{} for mode {}: '.format(self.__class__.__name__,
                                               self._mode.name)
            log.keyboard.debug(prefix + message)

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
        return MatchResult(match_type=QKeySequence.NoMatch,
                           command=None,
                           sequence=sequence)

    def _match_count(self, sequence: keyutils.KeySequence,
                     dry_run: bool) -> bool:
        """Try to match a key as count."""
        txt = str(sequence[-1])  # To account for sequences changed above.
        if (txt in string.digits and self._supports_count and
                not (not self._count and txt == '0')):
            self._debug_log("Trying match as count")
            assert len(txt) == 1, txt
            if not dry_run:
                self._count += txt
                self.keystring_updated.emit(self._count + str(self._sequence))
            return True
        return False

    def handle(self, e: QKeyEvent, *,
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
        key = Qt.Key(e.key())
        txt = str(keyutils.KeyInfo.from_event(e))
        self._debug_log("Got key: 0x{:x} / modifiers: 0x{:x} / text: '{}' / "
                        "dry_run {}".format(key, int(e.modifiers()), txt,
                                            dry_run))

        if keyutils.is_modifier_key(key):
            self._debug_log("Ignoring, only modifier")
            return QKeySequence.NoMatch

        try:
            sequence = self._sequence.append_event(e)
        except keyutils.KeyParseError as ex:
            self._debug_log("{} Aborting keychain.".format(ex))
            self.clear_keystring()
            return QKeySequence.NoMatch

        result = self._match_key(sequence)
        del sequence  # Enforce code below to use the modified result.sequence

        if result.match_type == QKeySequence.NoMatch:
            result = self._match_without_modifiers(result.sequence)
        if result.match_type == QKeySequence.NoMatch:
            result = self._match_key_mapping(result.sequence)
        if result.match_type == QKeySequence.NoMatch:
            was_count = self._match_count(result.sequence, dry_run)
            if was_count:
                return QKeySequence.ExactMatch

        if dry_run:
            return result.match_type

        self._sequence = result.sequence

        if result.match_type == QKeySequence.ExactMatch:
            assert result.command is not None
            self._debug_log("Definitive match for '{}'.".format(
                result.sequence))
            count = int(self._count) if self._count else None
            self.clear_keystring()
            self.execute(result.command, count)
        elif result.match_type == QKeySequence.PartialMatch:
            self._debug_log("No match for '{}' (added {})".format(
                result.sequence, txt))
            self.keystring_updated.emit(self._count + str(result.sequence))
        elif result.match_type == QKeySequence.NoMatch:
            self._debug_log("Giving up with '{}', no matches".format(
                result.sequence))
            self.clear_keystring()
        else:
            raise utils.Unreachable("Invalid match value {!r}".format(
                result.match_type))

        return result.match_type

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
        if self._sequence:
            self._debug_log("Clearing keystring (was: {}).".format(
                self._sequence))
            self._sequence = keyutils.KeySequence()
            self._count = ''
            self.keystring_updated.emit('')
