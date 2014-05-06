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

"""KeyChainParser for "hint" and "normal" modes.

Module attributes:
    STARTCHARS: Possible chars for starting a commandline input.
"""

import logging

from PyQt5.QtCore import pyqtSignal, Qt

import qutebrowser.utils.message as message
import qutebrowser.config.config as config
from qutebrowser.keyinput.keyparser import CommandKeyParser
from qutebrowser.utils.usertypes import enum


STARTCHARS = ":/?"
LastPress = enum('none', 'filtertext', 'keystring')


class NormalKeyParser(CommandKeyParser):

    """KeyParser for normalmode with added STARTCHARS detection."""

    def __init__(self, parent=None):
        super().__init__(parent, supports_count=True, supports_chains=True)
        self.read_config('keybind')

    def _handle_single_key(self, e):
        """Override _handle_single_key to abort if the key is a startchar.

        Args:
            e: the KeyPressEvent from Qt.

        Return:
            True if event has been handled, False otherwise.
        """
        txt = e.text().strip()
        if not self._keystring and any(txt == c for c in STARTCHARS):
            message.set_cmd_text(txt)
            return True
        return super()._handle_single_key(e)


class HintKeyParser(CommandKeyParser):

    """KeyChainParser for hints.

    Signals:
        fire_hint: When a hint keybinding was completed.
                   Arg: the keystring/hint string pressed.
        filter_hints: When the filter text changed.
                      Arg: the text to filter hints with.

    Attributes:
        _filtertext: The text to filter with.
        _last_press: The nature of the last keypress, a LastPress member.
    """

    fire_hint = pyqtSignal(str)
    filter_hints = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent, supports_count=False, supports_chains=True)
        self._filtertext = ''
        self._last_press = LastPress.none
        self.read_config('keybind.hint')

    def _handle_special_key(self, e):
        """Override _handle_special_key to handle string filtering.

        Return True if the keypress has been handled, and False if not.

        Args:
            e: the KeyPressEvent from Qt.

        Return:
            True if event has been handled, False otherwise.

        Emit:
            filter_hints: Emitted when filter string has changed.
            keystring_updated: Emitted when keystring has been changed.
        """
        logging.debug("Got special key {} text {}".format(e.key(), e.text()))
        if e.key() == Qt.Key_Backspace:
            logging.debug("Got backspace, mode {}, filtertext \"{}\", "
                          "keystring \"{}\"".format(
                              LastPress[self._last_press], self._filtertext,
                              self._keystring))
            if self._last_press == LastPress.filtertext and self._filtertext:
                self._filtertext = self._filtertext[:-1]
                self.filter_hints.emit(self._filtertext)
                return True
            elif self._last_press == LastPress.keystring and self._keystring:
                self._keystring = self._keystring[:-1]
                self.keystring_updated.emit(self._keystring)
                return True
            else:
                return super()._handle_special_key(e)
        elif config.get('hints', 'mode') != 'number':
            return super()._handle_special_key(e)
        elif not e.text():
            return super()._handle_special_key(e)
        else:
            self._filtertext += e.text()
            self.filter_hints.emit(self._filtertext)
            self._last_press = LastPress.filtertext
            return True

    def handle(self, e):
        """Handle a new keypress and call the respective handlers.

        Args:
            e: the KeyPressEvent from Qt

        Emit:
            keystring_updated: If a new keystring should be set.
        """
        handled = self._handle_single_key(e)
        if handled:
            self.keystring_updated.emit(self._keystring)
            self._last_press = LastPress.keystring
            return handled
        return self._handle_special_key(e)

    def execute(self, cmdstr, keytype, count=None):
        """Handle a completed keychain.

        Emit:
            fire_hint: Emitted if keytype is chain
        """
        if keytype == self.Type.chain:
            self.fire_hint.emit(cmdstr)
        else:
            # execute as command
            super().execute(cmdstr, keytype, count)

    def on_hint_strings_updated(self, strings):
        """Handler for HintManager's hint_strings_updated.

        Args:
            strings: A list of hint strings.
        """
        self.bindings = {s: s for s in strings}
        self._filtertext = ''
