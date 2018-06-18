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

import string

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
        request_leave: Emitted to request leaving a mode.
                       arg 0: Mode to leave.
                       arg 1: Reason for leaving.
                       arg 2: Ignore the request if we're not in that mode
    """

    keystring_updated = pyqtSignal(str)
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
            A tuple (matchtype, binding).
                matchtype: Match.definitive, Match.partial or Match.none.
                binding: - None with Match.partial/Match.none.
                         - The found binding with Match.definitive.
        """
        assert sequence
        assert not isinstance(sequence, str)
        result = QKeySequence.NoMatch

        for seq, cmd in self.bindings.items():
            assert not isinstance(seq, str), seq
            match = sequence.matches(seq)
            if match == QKeySequence.ExactMatch:
                return match, cmd
            elif match == QKeySequence.PartialMatch:
                result = QKeySequence.PartialMatch

        return result, None

    def _match_without_modifiers(self, sequence):
        """Try to match a key with optional modifiers stripped."""
        self._debug_log("Trying match without modifiers")
        sequence = sequence.strip_modifiers()
        match, binding = self._match_key(sequence)
        return match, binding, sequence

    def _match_key_mapping(self, sequence):
        """Try to match a key in bindings.key_mappings."""
        self._debug_log("Trying match with key_mappings")
        mapped = sequence.with_mappings(config.val.bindings.key_mappings)
        if sequence != mapped:
            self._debug_log("Mapped {} -> {}".format(
                sequence, mapped))
            match, binding = self._match_key(mapped)
            sequence = mapped
            return match, binding, sequence
        return QKeySequence.NoMatch, None, sequence

    def _match_count(self, sequence, dry_run):
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

        try:
            sequence = self._sequence.append_event(e)
        except keyutils.KeyParseError as ex:
            self._debug_log("{} Aborting keychain.".format(ex))
            self.clear_keystring()
            return QKeySequence.NoMatch

        match, binding = self._match_key(sequence)
        if match == QKeySequence.NoMatch:
            match, binding, sequence = self._match_without_modifiers(sequence)
        if match == QKeySequence.NoMatch:
            match, binding, sequence = self._match_key_mapping(sequence)
        if match == QKeySequence.NoMatch:
            was_count = self._match_count(sequence, dry_run)
            if was_count:
                return QKeySequence.ExactMatch

        if dry_run:
            return match

        self._sequence = sequence

        if match == QKeySequence.ExactMatch:
            self._debug_log("Definitive match for '{}'.".format(
                sequence))
            count = int(self._count) if self._count else None
            self.clear_keystring()
            self.execute(binding, count)
        elif match == QKeySequence.PartialMatch:
            self._debug_log("No match for '{}' (added {})".format(
                sequence, txt))
            self.keystring_updated.emit(self._count + str(sequence))
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
