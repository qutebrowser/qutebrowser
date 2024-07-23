# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""TabIndex displayed in the statusbar."""

from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.mainwindow.statusbar.item import StatusBarItem


class TabIndexWidget(textbase.TextBaseWidget):

    """Shows current tab index and number of tabs in the statusbar."""


class TabIndex(StatusBarItem):
    def on_tab_index_changed(self, current, count):
        """Update tab index when tab changed."""
        self.widget.setText('[{}/{}]'.format(current + 1, count))
