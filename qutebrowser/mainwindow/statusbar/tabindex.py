# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""TabIndex displayed in the statusbar."""

from qutebrowser.qt.core import pyqtSlot

from qutebrowser.mainwindow.statusbar import textbase


class TabIndexWidget(textbase.TextBase):

    """Shows current tab index and number of tabs in the statusbar."""

    @pyqtSlot(int, int)
    def on_tab_index_changed(self, current, count):
        """Update tab index when tab changed."""
        self.setText('[{}/{}]'.format(current + 1, count))


class TabIndex:
    def __init__(self, widget: TabIndexWidget):
        self.widget = widget

    def enable(self):
        self.widget.show()

    def disable(self):
        self.widget.hide()
