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

from qutebrowser.keyinput.keyparser import KeyParser


class HintKeyParser(KeyParser):

    """KeyChainParser for hints.

    Signals:
        fire_hint: When a hint keybinding was completed.
                   Arg: the keystring/hint string pressed.
        abort_hinting: Esc pressed, so abort hinting.
    """

    fire_hint = pyqtSignal(str)
    abort_hinting = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, supports_count=False, supports_chains=True)

    def _handle_special_key(self, e):
        """Handle the escape key.

        FIXME make this more generic

        Emit:
            abort_hinting: Emitted if hinting was aborted.
        """
        if e.key() == Qt.Key_Escape:
            self._keystring = ''
            self.abort_hinting.emit()
            return True
        return False

    def execute(self, cmdstr, _count=None):
        """Handle a completed keychain.

        Emit:
            fire_hint: Always emitted.
        """
        self.fire_hint.emit(cmdstr)

    def on_hint_strings_updated(self, strings):
        """Handler for HintManager's hint_strings_updated.

        Args:
            strings: A list of hint strings.
        """
        self.bindings = {s: s for s in strings}
