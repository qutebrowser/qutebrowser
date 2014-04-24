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

"""KeyParser for "insert" mode."""

from PyQt5.QtCore import pyqtSignal, Qt

import qutebrowser.keyinput.modes as modes
from qutebrowser.keyinput.keyparser import KeyParser


class InsertKeyParser(KeyParser):

    """KeyParser for insert mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.read_config('keybind.insert')

    def execute(self, cmdstr, count=None):
        """Handle a completed keychain."""
        if cmdstr == '<leave>':
            modes.leave("insert")
