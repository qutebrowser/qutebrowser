#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

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

"""Small test script to show key presses.

Use python3 -m scripts.keytester to launch it.
"""

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QHBoxLayout

from qutebrowser.utils import utils


class KeyWidget(QWidget):

    """Widget displaying key presses."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._label = QLabel(text="Waiting for keypress...")
        self._layout.addWidget(self._label)

    def keyPressEvent(self, e):
        """Show pressed keys."""
        lines = [
            str(utils.keyevent_to_string(e)),
            '',
            'key: 0x{:x}'.format(int(e.key())),
            'modifiers: 0x{:x}'.format(int(e.modifiers())),
            'text: {!r}'.format(e.text()),
        ]
        self._label.setText('\n'.join(lines))


app = QApplication([])
w = KeyWidget()
w.show()
app.exec_()
