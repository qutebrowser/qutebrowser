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

from qutebrowser.qt.core import Qt, QTimer

from qutebrowser.mainwindow.statusbar import textbase


class Clock(textbase.TextBase):

    """Shows current time and date in the statusbar."""

    UPDATE_DELAY = 500  # ms

    def __init__(self, parent=None):
        super().__init__(parent, elidemode=Qt.TextElideMode.ElideNone)
        self.format = ""

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._show_time)

    def _show_time(self):
        """Set text to current time, using self.format as format-string."""
        self.setText(datetime.now().strftime(self.format))

    def hideEvent(self, event):
        """Stop timer when widget is hidden."""
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        """Override showEvent to show time and start self.timer for updating."""
        self.timer.start(Clock.UPDATE_DELAY)
        self._show_time()
        super().showEvent(event)
