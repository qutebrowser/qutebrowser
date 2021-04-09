# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Clock displayed in the statusbar."""
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer

from qutebrowser.mainwindow.statusbar import textbase


class Clock(textbase.TextBase):

    """Shows current time and date in the statusbar."""

    def __init__(self, parent=None):
        super().__init__(parent, elidemode=Qt.ElideNone)
        self.format = ""

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._show_time)

    def _show_time(self):
        """Set text to current time, using self.format as format-string."""
        self.setText(datetime.now().strftime(self.format))

    def show(self) -> None:
        """Override show() to show time and start self.timer for updating."""
        self.timer.start(100)
        self._show_time()
        super().show()
