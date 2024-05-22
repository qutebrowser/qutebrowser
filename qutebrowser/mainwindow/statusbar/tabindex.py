# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""TabIndex displayed in the statusbar."""

from qutebrowser.mainwindow.statusbar.widget import StatusBarWidget
from qutebrowser.qt.core import pyqtSlot

from qutebrowser.mainwindow.statusbar import textbase


class TabIndex(StatusBarWidget, textbase.TextBase):

    """Shows current tab index and number of tabs in the statusbar."""

    def enable(self):
        self.show()

    def disable(self):
        self.hide()

    @pyqtSlot(int, int)
    def on_tab_index_changed(self, current, count):
        """Update tab index when tab changed."""
        self.setText('[{}/{}]'.format(current + 1, count))
