# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Base class for vim-like key sequence parser."""

from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtGui import QKeySequence

from qutebrowser.config import config
from qutebrowser.utils import usertypes, log, utils
from qutebrowser.keyinput import keyutils


class BaseKeyParser(QObject):

    """Parser for vim-like key sequences and shortcuts.

    Not intended to be instantiated directly. Subclasses have to override
    execute() to do whatever they want to.

    Class Attributes:
        Match: types of a match between a binding and the keystring.
            partial: No keychain matched yet, but it's still possible in the
                     future.
            definitive: Keychain matches exactly.
            none: No more matches possible.

        do_log: Whether to log keypresses or not.
        passthrough: Whether unbound keys should be passed through with this
                     handler.

    Attributes:
        bindings: Bound key bindings
        _win_id: The window ID this keyparser is associated with.
        _sequence: The currently entered key sequence
        _modename: The name of the input mode associated with this keyparser.
        _supports_count: Whether count is supported

    Signals:
        keystring_updated: Emitted when the keystring is updated.
                           arg: New keystring.
        bindings_matched: Emitted when matched bindings are found.
                          arg 0: Whether the count was entered.
                          arg 1: Matching sequence.
                          arg 2: Matched bindings dictionary.
        request_leave: Emitted to request leaving a mode.
                       arg 0: Mode to leave.
                       arg 1: Reason for leaving.
                       arg 2: Ignore the request if we're not in that mode
    """

    keystring_updated = pyqtSignal(str)
    bindings_matched = pyqtSignal(bool, keyutils.KeySequence, dict)
    request_leave = pyqtSignal(usertypes.KeyMode, str, bool)
    do_log = True
    passthrough = False

    def __init__(self, win_id, parent=None, supports_count=True):
        super().__init__(parent)
        self._win_id = win_id
        self._modename = None
        self._sequence = keyutils.KeySequence()
        self._count = ''
        self._supports_count = supports_count
        self.bindings = {}
        config.instance.changed.connect(self._on_config_changed)

    def __repr__(self):
        return utils.get_repr(self, supports_count=self._supports_count)

    def _debug_log(self, message):
        """Log a message to the debug log if logging is active.

        Args:
            message: The message to log.
        """
        if self.do_log:
            log.keyboard.debug(message)

    def _match_key(self, sequence):
        """Try to match a given keystring with any bound keychain.

        Args:
            sequence: The command string to find.

        Return:
            A tuple (matchtype, bindings).
                matchtype: Match.definitive, Match.partial or Match.none.
                bindings: - Empty dict for Match.none.
                          - Dict of found bindings for Match.partial.
                          - Dict with one binding for Match.definitive.
        """
        assert sequence
        assert not isinstance(sequence, str)
        result = QKeySequence.NoMatch
        bindings = {}

        for seq, cmd in self.bindings.items():
            assert not isinstance(seq, str), seq
            match = sequence.matches(seq)
            if match == QKeySequence.ExactMatch:
                return (match, {seq: cmd})
            elif match == QKeySequence.PartialMatch:
                result = QKeySequence.PartialMatch
                bindings[seq] = cmd

        return (result, bindings)

    def handle(self, e, *, dry_run=False):
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
        key = e.key()
        txt = str(keyutils.KeyInfo.from_event(e))
        self._debug_log("Got key: 0x{:x} / modifiers: 0x{:x} / text: '{}' / "
                        "dry_run {}".format(key, int(e.modifiers()), txt,
                                            dry_run))

        if keyutils.is_modifier_key(key):
            self._debug_log("Ignoring, only modifier")
            return QKeySequence.NoMatch

        if (txt.isdigit() and self._supports_count and not
                (not self._count and txt == '0')):
            assert len(txt) == 1, txt
            if not dry_run:
                self._count += txt
            return QKeySequence.ExactMatch

        try:
            sequence = self._sequence.append_event(e)
        except keyutils.KeyParseError as ex:
            self._debug_log("{} Aborting keychain.".format(ex))
            self.clear_keystring()
            return QKeySequence.NoMatch

        match, bindings = self._match_key(sequence)
        mapped = sequence.with_mappings(config.val.bindings.key_mappings)
        mapped_match = None

        if sequence != mapped and match != QKeySequence.ExactMatch:
            self._debug_log("Mapped {} -> {}".format(
                sequence, mapped))
            mapped_match, mapped_bindings = self._match_key(mapped)
            if (match == QKeySequence.NoMatch or
                    mapped_match == QKeySequence.ExactMatch):
                match = mapped_match
                bindings = mapped_bindings
            else:
                bindings = {**bindings, **mapped_bindings}

        if dry_run:
            return match

        self._sequence = sequence

        if match == QKeySequence.ExactMatch:
            if mapped_match is not None:
                key_seq = mapped
            else:
                key_seq = sequence
            self._debug_log("Definitive match for '{}'.".format(
                key_seq))
            count = int(self._count) if self._count else None
            self.clear_keystring()
            self.execute(bindings[key_seq], count)
        elif match == QKeySequence.PartialMatch:
            self._debug_log("No match for '{}' (added {})".format(
                sequence, txt))
            self.keystring_updated.emit(self._count + str(sequence))
            self.bindings_matched.emit(bool(self._count), sequence, bindings)
        elif match == QKeySequence.NoMatch:
            self._debug_log("Giving up with '{}', no matches".format(
                sequence))
            self.clear_keystring()
        else:
            raise utils.Unreachable("Invalid match value {!r}".format(match))

        return match

    @config.change_filter('bindings')
    def _on_config_changed(self):
        self._read_config()

    def _read_config(self, modename=None):
        """Read the configuration.

        Config format: key = command, e.g.:
            <Ctrl+Q> = quit

        Args:
            modename: Name of the mode to use.
        """
        if modename is None:
            if self._modename is None:
                raise ValueError("read_config called with no mode given, but "
                                 "None defined so far!")
            modename = self._modename
        else:
            self._modename = modename
        self.bindings = {}

        for key, cmd in config.key_instance.get_bindings_for(modename).items():
            assert not isinstance(key, str), key
            assert cmd
            self.bindings[key] = cmd

    def execute(self, cmdstr, count=None):
        """Handle a completed keychain.

        Args:
            cmdstr: The command to execute as a string.
            count: The count if given.
        """
        raise NotImplementedError

    def clear_keystring(self):
        """Clear the currently entered key sequence."""
        if self._sequence:
            self._debug_log("Clearing keystring (was: {}).".format(
                self._sequence))
            self._sequence = keyutils.KeySequence()
            self._count = ''
            self.keystring_updated.emit('')
            self.bindings_matched.emit(bool(self._count),
                    keyutils.KeySequence(), {})
