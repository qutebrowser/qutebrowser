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

from PyQt5.QtCore import pyqtSignal, Qt, QObject
from PyQt5.QtGui import QKeySequence


class KeyParser(QObject):

    """Parser for vim-like key sequences.

    Not intended to be instantiated directly. Subclasses have to override
    execute() to do whatever they want to.

    Class Attributes:
        MATCH_PARTIAL: Constant for a partial match (no keychain matched yet,
                       but it's still possible in the future.
        MATCH_DEFINITIVE: Constant for a full match (keychain matches exactly).
        MATCH_NONE: Constant for no match (no more matches possible).
        supports_count: If the keyparser should support counts.

    Attributes:
        _keystring: The currently entered key sequence
        _bindings: Bound keybindings
        _modifier_bindings: Bound modifier bindings.

    Signals:
        keystring_updated: Emitted when the keystring is updated.
                           arg: New keystring.
    """

    keystring_updated = pyqtSignal(str)

    MATCH_PARTIAL = 0
    MATCH_DEFINITIVE = 1
    MATCH_NONE = 2

    supports_count = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self._keystring = ''
        self._bindings = {}
        self._modifier_bindings = {}

    def _handle_modifier_key(self, e):
        """Handle a new keypress with modifiers.

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
        if not mod & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
            # won't be a shortcut with modifiers
            return False
        for (mask, s) in modmask2str.items():
            if mod & mask:
                modstr += s + '+'
        keystr = QKeySequence(e.key()).toString()
        try:
            cmdstr = self._modifier_bindings[modstr + keystr]
        except KeyError:
            logging.debug('No binding found for {}.'.format(modstr + keystr))
            return True
        self.execute(cmdstr)
        return True

    def _handle_single_key(self, e):
        """Handle a new keypress with a single key (no modifiers).

        Separate the keypress into count/command, then check if it matches
        any possible command, and either run the command, ignore it, or
        display an error.

        Args:
            e: the KeyPressEvent from Qt.
        """
        # FIXME maybe we can do this in an easier way by using QKeySeqyence
        # which has a matches method.
        logging.debug('Got key: {} / text: "{}"'.format(e.key(), e.text()))
        txt = e.text().strip()
        if not txt:
            logging.debug('Ignoring, no text')
            return

        self._keystring += txt

        if self.supports_count:
            (countstr, cmdstr_needle) = re.match(r'^(\d*)(.*)',
                                                 self._keystring).groups()
        else:
            countstr = None
            cmdstr_needle = self._keystring

        if not cmdstr_needle:
            return

        # FIXME this doesn't handle ambigious keys correctly.
        #
        # If a keychain is ambigious, we probably should set up a QTimer with a
        # configurable timeout, which triggers cmd.run() when expiring. Then
        # when we enter _handle() again in time we stop the timer.

        (match, cmdstr_hay) = self._match_key(cmdstr_needle)

        if match == self.MATCH_DEFINITIVE:
            pass
        elif match == self.MATCH_PARTIAL:
            logging.debug('No match for "{}" (added {})'.format(
                self._keystring, txt))
            return
        elif match == self.MATCH_NONE:
            logging.debug('Giving up with "{}", no matches'.format(
                self._keystring))
            self._keystring = ''
            return

        self._keystring = ''
        count = int(countstr) if countstr else None
        self.execute(cmdstr_hay, count=count)
        return

    def _match_key(self, cmdstr_needle):
        """Try to match a given keystring with any bound keychain.

        Args:
            cmdstr_needle: The command string to find.

        Return:
            A tuple (matchtype, hay) where matchtype is MATCH_DEFINITIVE,
            MATCH_PARTIAL or MATCH_NONE and hay is the long keystring where the
            part was found in.
        """
        try:
            cmdstr_hay = self._bindings[cmdstr_needle]
            return (self.MATCH_DEFINITIVE, cmdstr_hay)
        except KeyError:
            # No definitive match, check if there's a chance of a partial match
            for hay in self._bindings:
                try:
                    if cmdstr_needle[-1] == hay[len(cmdstr_needle) - 1]:
                        return (self.MATCH_PARTIAL, None)
                except IndexError:
                    # current cmd is shorter than our cmdstr_needle, so it
                    # won't match
                    continue
            # no definitive and no partial matches if we arrived here
            return (self.MATCH_NONE, None)

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

    def execute(self, cmdstr, count=None):
        """Execute an action when a binding is triggered."""
        raise NotImplementedError

    def handle(self, e):
        """Handle a new keypress and call the respective handlers.

        Args:
            e: the KeyPressEvent from Qt

        Emit:
            keystring_updated: If a new keystring should be set.
        """
        handled = self._handle_modifier_key(e)
        if not handled:
            self._handle_single_key(e)
            self.keystring_updated.emit(self._keystring)
