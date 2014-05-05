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

"""Base class for vim-like keysequence parser."""

import re
import logging
from functools import partial

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QObject, QTimer
from PyQt5.QtGui import QKeySequence

import qutebrowser.config.config as config
from qutebrowser.utils.usertypes import enum


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

        Types: type of a keybinding.
            chain: execute() was called via a chain-like keybinding
            special: execute() was called via a special keybinding

    Attributes:
        bindings: Bound keybindings
        special_bindings: Bound special bindings (<Foo>).
        _keystring: The currently entered key sequence
        _timer: QTimer for delayed execution.
        _confsectname: The name of the configsection.
        _supports_count: Whether count is supported
        _supports_chains: Whether keychains are supported

    Signals:
        keystring_updated: Emitted when the keystring is updated.
                           arg: New keystring.
    """

    keystring_updated = pyqtSignal(str)

    Match = enum('partial', 'definitive', 'ambiguous', 'none')
    Type = enum('chain', 'special')

    def __init__(self, parent=None, supports_count=None,
                 supports_chains=False):
        super().__init__(parent)
        self._timer = None
        self._confsectname = None
        self._keystring = ''
        if supports_count is None:
            supports_count = supports_chains
        self._supports_count = supports_count
        self._supports_chains = supports_chains
        self.bindings = {}
        self.special_bindings = {}

    def _normalize_keystr(self, keystr):
        """Normalize a keystring like Ctrl-Q to a keystring like Ctrl+Q.

        Args:
            keystr: The key combination as a string.

        Return:
            The normalized keystring.
        """
        replacements = [
            ('Control', 'Ctrl'),
            ('Windows', 'Meta'),
            ('Mod1', 'Alt'),
            ('Mod4', 'Meta'),
        ]
        for (orig, repl) in replacements:
            keystr = keystr.replace(orig, repl)
        for mod in ['Ctrl', 'Meta', 'Alt', 'Shift']:
            keystr = keystr.replace(mod + '-', mod + '+')
        keystr = QKeySequence(keystr).toString()
        return keystr

    def _handle_special_key(self, e):
        """Handle a new keypress with special keys (<Foo>).

        Return True if the keypress has been handled, and False if not.

        Args:
            e: the KeyPressEvent from Qt.

        Return:
            True if event has been handled, False otherwise.
        """
        modmask2str = {
            Qt.ControlModifier: 'Ctrl',
            Qt.AltModifier: 'Alt',
            Qt.MetaModifier: 'Meta',
            Qt.ShiftModifier: 'Shift'
        }
        if e.key() in [Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta]:
            # Only modifier pressed
            return False
        mod = e.modifiers()
        modstr = ''
        for (mask, s) in modmask2str.items():
            if mod & mask:
                modstr += s + '+'
        keystr = QKeySequence(e.key()).toString().replace("Backtab", "Tab")
        try:
            cmdstr = self.special_bindings[modstr + keystr]
        except KeyError:
            logging.debug("No binding found for {}.".format(modstr + keystr))
            return False
        self.execute(cmdstr, self.Type.special)
        return True

    def _handle_single_key(self, e):
        """Handle a new keypress with a single key (no modifiers).

        Separate the keypress into count/command, then check if it matches
        any possible command, and either run the command, ignore it, or
        display an error.

        Args:
            e: the KeyPressEvent from Qt.

        Return:
            True if event has been handled, False otherwise.
        """
        logging.debug("Got key: {} / text: '{}'".format(e.key(), e.text()))
        txt = e.text().strip()
        if not txt:
            logging.debug("Ignoring, no text")
            return False

        self._stop_delayed_exec()
        self._keystring += txt

        if self._supports_count:
            (countstr, cmd_input) = re.match(r'^(\d*)(.*)',
                                             self._keystring).groups()
            count = int(countstr) if countstr else None
        else:
            cmd_input = self._keystring
            count = None

        if not cmd_input:
            # Only a count, no command yet, but we handled it
            return True

        (match, binding) = self._match_key(cmd_input)

        if match == self.Match.definitive:
            self._keystring = ''
            self.execute(binding, self.Type.chain, count)
        elif match == self.Match.ambiguous:
            self._handle_ambiguous_match(binding, count)
        elif match == self.Match.partial:
            logging.debug("No match for \"{}\" (added {})".format(
                self._keystring, txt))
        elif match == self.Match.none:
            logging.debug("Giving up with \"{}\", no matches".format(
                self._keystring))
            self._keystring = ''
            return False
        return True

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

    def _stop_delayed_exec(self):
        """Stop a delayed execution if any is running."""
        if self._timer is not None:
            logging.debug("Stopping delayed execution.")
            self._timer.stop()
            self._timer = None

    def _handle_ambiguous_match(self, binding, count):
        """Handle an ambiguous match.

        Args:
            binding: The command-string to execute.
            count: The count to pass.
        """
        logging.debug("Ambiguous match for \"{}\"".format(self._keystring))
        time = config.get('input', 'timeout')
        if time == 0:
            # execute immediately
            self._keystring = ''
            self.execute(binding, self.Type.chain, count)
        else:
            # execute in `time' ms
            logging.debug("Scheduling execution of {} in {}ms".format(binding,
                                                                      time))
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(time)
            self._timer.timeout.connect(partial(self.delayed_exec, binding,
                                                count))
            self._timer.start()

    def delayed_exec(self, command, count):
        """Execute a delayed command.

        Args:
            command/count: As if passed to self.execute()

        Emit:
            keystring_updated to do a delayed update.
        """
        logging.debug("Executing delayed command now!")
        self._timer = None
        self._keystring = ''
        self.keystring_updated.emit(self._keystring)
        self.execute(command, self.Type.chain, count)

    def handle(self, e):
        """Handle a new keypress and call the respective handlers.

        Args:
            e: the KeyPressEvent from Qt

        Emit:
            keystring_updated: If a new keystring should be set.
        """
        handled = self._handle_special_key(e)
        if handled or not self._supports_chains:
            return handled
        handled = self._handle_single_key(e)
        self.keystring_updated.emit(self._keystring)
        return handled

    def read_config(self, sectname=None):
        """Read the configuration.

        Config format: key = command, e.g.:
            <Ctrl+Q> = quit

        Args:
            sectname: Name of the section to read.
        """
        if sectname is None:
            if self._confsectname is None:
                raise ValueError("read_config called with no section, but "
                                 "None defined so far!")
            sectname = self._confsectname
        else:
            self._confsectname = sectname
        sect = config.section(sectname)
        if not sect.items():
            logging.warn("No keybindings defined!")
        for (key, cmd) in sect.items():
            if not cmd:
                continue
            elif key.startswith('<') and key.endswith('>'):
                keystr = self._normalize_keystr(key[1:-1])
                logging.debug("registered special key: {} -> {}".format(keystr,
                                                                        cmd))
                self.special_bindings[keystr] = cmd
            elif self._supports_chains:
                logging.debug("registered key: {} -> {}".format(key, cmd))
                self.bindings[key] = cmd
            else:
                logging.warn(
                    "Ignoring keychain \"{}\" in section \"{}\" because "
                    "keychains are not supported there.".format(key, sectname))

    def execute(self, cmdstr, keytype, count=None):
        """Handle a completed keychain.

        Args:
            cmdstr: The command to execute as a string.
            keytype: Type.chain or Type.special
            count: The count if given.
        """
        raise NotImplementedError

    @pyqtSlot(str, str)
    def on_config_changed(self, section, _option):
        """Re-read the config if a keybinding was changed."""
        if self._confsectname is None:
            raise AttributeError("on_config_changed called but no section "
                                 "defined!")
        if section == self._confsectname:
            self.read_config()
