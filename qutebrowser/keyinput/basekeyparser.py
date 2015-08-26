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

"""Base class for vim-like key sequence parser."""

import re
import functools
import unicodedata

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject

from qutebrowser.config import config
from qutebrowser.utils import usertypes, log, utils, objreg


class BaseKeyParser(QObject):

    """Parser for vim-like key sequences and shortcuts.

    Not intended to be instantiated directly. Subclasses have to override
    execute() to do whatever they want to.

    Class Attributes:
        Match: types of a match between a binding and the keystring.
            partial: No keychain matched yet, but it's still possible in the
                     future.
            definitive: Keychain matches exactly.
            ambiguous: There are both a partial and a definitive match.
            none: No more matches possible.

        Types: type of a key binding.
            chain: execute() was called via a chain-like key binding
            special: execute() was called via a special key binding

        do_log: Whether to log keypresses or not.
        passthrough: Whether unbound keys should be passed through with this
                     handler.

    Attributes:
        bindings: Bound key bindings
        special_bindings: Bound special bindings (<Foo>).
        _win_id: The window ID this keyparser is associated with.
        _warn_on_keychains: Whether a warning should be logged when binding
                            keychains in a section which does not support them.
        _keystring: The currently entered key sequence
        _ambiguous_timer: Timer for delayed execution with ambiguous bindings.
        _modename: The name of the input mode associated with this keyparser.
        _supports_count: Whether count is supported
        _supports_chains: Whether keychains are supported

    Signals:
        keystring_updated: Emitted when the keystring is updated.
                           arg: New keystring.
    """

    keystring_updated = pyqtSignal(str)
    do_log = True
    passthrough = False

    Match = usertypes.enum('Match', ['partial', 'definitive', 'ambiguous',
                                     'other', 'none'])
    Type = usertypes.enum('Type', ['chain', 'special'])

    def __init__(self, win_id, parent=None, supports_count=None,
                 supports_chains=False):
        super().__init__(parent)
        self._win_id = win_id
        self._ambiguous_timer = usertypes.Timer(self, 'ambiguous-match')
        self._ambiguous_timer.setSingleShot(True)
        self._modename = None
        self._keystring = ''
        if supports_count is None:
            supports_count = supports_chains
        self._supports_count = supports_count
        self._supports_chains = supports_chains
        self._warn_on_keychains = True
        self.bindings = {}
        self.special_bindings = {}

    def __repr__(self):
        return utils.get_repr(self, supports_count=self._supports_count,
                              supports_chains=self._supports_chains)

    def _debug_log(self, message):
        """Log a message to the debug log if logging is active.

        Args:
            message: The message to log.
        """
        if self.do_log:
            log.keyboard.debug(message)

    def _handle_special_key(self, e):
        """Handle a new keypress with special keys (<Foo>).

        Return True if the keypress has been handled, and False if not.

        Args:
            e: the KeyPressEvent from Qt.

        Return:
            True if event has been handled, False otherwise.
        """
        binding = utils.keyevent_to_string(e)
        if binding is None:
            self._debug_log("Ignoring only-modifier keyeevent.")
            return False
        binding = binding.lower()
        try:
            cmdstr = self.special_bindings[binding]
        except KeyError:
            self._debug_log("No binding found for {}.".format(binding))
            return False
        self.execute(cmdstr, self.Type.special)
        return True

    def _split_count(self):
        """Get count and command from the current keystring.

        Return:
            A (count, command) tuple.
        """
        if self._supports_count:
            (countstr, cmd_input) = re.match(r'^(\d*)(.*)',
                                             self._keystring).groups()
            count = int(countstr) if countstr else None
            if count == 0 and not cmd_input:
                cmd_input = self._keystring
                count = None
        else:
            cmd_input = self._keystring
            count = None
        return count, cmd_input

    def _handle_single_key(self, e):
        """Handle a new keypress with a single key (no modifiers).

        Separate the keypress into count/command, then check if it matches
        any possible command, and either run the command, ignore it, or
        display an error.

        Args:
            e: the KeyPressEvent from Qt.

        Return:
            A self.Match member.
        """
        txt = e.text()
        key = e.key()
        self._debug_log("Got key: 0x{:x} / text: '{}'".format(key, txt))

        if len(txt) == 1:
            category = unicodedata.category(txt)
            is_control_char = (category == 'Cc')
        else:
            is_control_char = False

        if (not txt) or is_control_char:
            self._debug_log("Ignoring, no text char")
            return self.Match.none

        self._stop_timers()
        self._keystring += txt

        count, cmd_input = self._split_count()

        if not cmd_input:
            # Only a count, no command yet, but we handled it
            return self.Match.other

        match, binding = self._match_key(cmd_input)

        if match == self.Match.definitive:
            self._debug_log("Definitive match for '{}'.".format(
                self._keystring))
            self._keystring = ''
            self.execute(binding, self.Type.chain, count)
        elif match == self.Match.ambiguous:
            self._debug_log("Ambiguous match for '{}'.".format(
                self._keystring))
            self._handle_ambiguous_match(binding, count)
        elif match == self.Match.partial:
            self._debug_log("No match for '{}' (added {})".format(
                self._keystring, txt))
        elif match == self.Match.none:
            self._debug_log("Giving up with '{}', no matches".format(
                self._keystring))
            self._keystring = ''
        else:
            raise AssertionError("Invalid match value {!r}".format(match))
        return match

    def _match_key(self, cmd_input):
        """Try to match a given keystring with any bound keychain.

        Args:
            cmd_input: The command string to find.

        Return:
            A tuple (matchtype, binding).
                matchtype: Match.definitive, Match.ambiguous, Match.partial or
                           Match.none
                binding: - None with Match.partial/Match.none
                         - The found binding with Match.definitive/
                           Match.ambiguous
        """
        # A (cmd_input, binding) tuple (k, v of bindings) or None.
        definitive_match = None
        partial_match = False
        # Check definitive match
        try:
            definitive_match = (cmd_input, self.bindings[cmd_input])
        except KeyError:
            pass
        # Check partial match
        for binding in self.bindings:
            if definitive_match is not None and binding == definitive_match[0]:
                # We already matched that one
                continue
            elif binding.startswith(cmd_input):
                partial_match = True
                break
        if definitive_match is not None and partial_match:
            return (self.Match.ambiguous, definitive_match[1])
        elif definitive_match is not None:
            return (self.Match.definitive, definitive_match[1])
        elif partial_match:
            return (self.Match.partial, None)
        else:
            return (self.Match.none, None)

    def _stop_timers(self):
        """Stop a delayed execution if any is running."""
        if self._ambiguous_timer.isActive() and self.do_log:
            log.keyboard.debug("Stopping delayed execution.")
        self._ambiguous_timer.stop()
        try:
            self._ambiguous_timer.timeout.disconnect()
        except TypeError:
            # no connections
            pass

    def _handle_ambiguous_match(self, binding, count):
        """Handle an ambiguous match.

        Args:
            binding: The command-string to execute.
            count: The count to pass.
        """
        self._debug_log("Ambiguous match for '{}'".format(self._keystring))
        time = config.get('input', 'timeout')
        if time == 0:
            # execute immediately
            self._keystring = ''
            self.execute(binding, self.Type.chain, count)
        else:
            # execute in `time' ms
            self._debug_log("Scheduling execution of {} in {}ms".format(
                binding, time))
            self._ambiguous_timer.setInterval(time)
            self._ambiguous_timer.timeout.connect(
                functools.partial(self.delayed_exec, binding, count))
            self._ambiguous_timer.start()

    def delayed_exec(self, command, count):
        """Execute a delayed command.

        Args:
            command/count: As if passed to self.execute()
        """
        self._debug_log("Executing delayed command now!")
        self._keystring = ''
        self.keystring_updated.emit(self._keystring)
        self.execute(command, self.Type.chain, count)

    def handle(self, e):
        """Handle a new keypress and call the respective handlers.

        Args:
            e: the KeyPressEvent from Qt

        Return:
            True if the event was handled, False otherwise.
        """
        handled = self._handle_special_key(e)

        if handled or not self._supports_chains:
            return handled
        match = self._handle_single_key(e)
        self.keystring_updated.emit(self._keystring)
        return match != self.Match.none

    def read_config(self, modename=None):
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
        self.special_bindings = {}
        keyconfparser = objreg.get('key-config')
        for (key, cmd) in keyconfparser.get_bindings_for(modename).items():
            assert cmd
            self._parse_key_command(modename, key, cmd)

    def _parse_key_command(self, modename, key, cmd):
        """Parse the keys and their command and store them in the object."""
        if key.startswith('<') and key.endswith('>'):
            keystr = utils.normalize_keystr(key[1:-1])
            self.special_bindings[keystr] = cmd
        elif self._supports_chains:
            self.bindings[key] = cmd
        elif self._warn_on_keychains:
            log.keyboard.warning(
                "Ignoring keychain '{}' in mode '{}' because "
                "keychains are not supported there."
                .format(key, modename))

    def execute(self, cmdstr, keytype, count=None):
        """Handle a completed keychain.

        Args:
            cmdstr: The command to execute as a string.
            keytype: Type.chain or Type.special
            count: The count if given.
        """
        raise NotImplementedError

    @pyqtSlot(str)
    def on_keyconfig_changed(self, mode):
        """Re-read the config if a key binding was changed."""
        if self._modename is None:
            raise AssertionError("on_keyconfig_changed called but no section "
                                 "defined!")
        if mode == self._modename:
            self.read_config()

    def clear_keystring(self):
        """Clear the currently entered key sequence."""
        self._debug_log("discarding keystring '{}'.".format(self._keystring))
        self._keystring = ''
        self.keystring_updated.emit(self._keystring)
