# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Clock displayed in the statusbar."""
from datetime import datetime

from qutebrowser.qt.core import Qt

from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.utils import usertypes


class Clock(textbase.TextBase):

    """Shows current time and date in the statusbar."""

    UPDATE_DELAY = 500  # ms

    def __init__(self, parent=None):
        super().__init__(parent, elidemode=Qt.TextElideMode.ElideNone)
        self.format = ""

        self.timer = usertypes.Timer(self)
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
