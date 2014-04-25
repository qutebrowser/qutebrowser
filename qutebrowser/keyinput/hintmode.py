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

"""KeyChainParser for "hint" mode."""

from PyQt5.QtCore import pyqtSignal, Qt

from qutebrowser.keyinput.keyparser import CommandKeyParser


class HintKeyParser(CommandKeyParser):

    """KeyChainParser for hints.

    Signals:
        fire_hint: When a hint keybinding was completed.
                   Arg: the keystring/hint string pressed.
    """

    fire_hint = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent, supports_count=False, supports_chains=True)
        self.read_config('keybind.hint')

    def execute(self, cmdstr, keytype, count=None):
        """Handle a completed keychain.

        Emit:
            fire_hint: Emitted if keytype is TYPE_CHAIN
        """
        if keytype == self.TYPE_CHAIN:
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
