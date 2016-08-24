# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Scroll percentage displayed in the statusbar."""

from PyQt5.QtCore import pyqtSlot

from qutebrowser.browser import browsertab
from qutebrowser.mainwindow.statusbar import textbase


class Percentage(textbase.TextBase):

    """Reading percentage displayed in the statusbar."""

    def __init__(self, parent=None):
        """Constructor. Set percentage to 0%."""
        super().__init__(parent)
        self.set_perc(0, 0)

    @pyqtSlot(int, int)
    def set_perc(self, x, y):  # pylint: disable=unused-argument
        """Setter to be used as a Qt slot.

        Args:
            x: The x percentage (int), currently ignored.
            y: The y percentage (int)
        """
        if y == 0:
            self.setText('[top]')
        elif y == 100:
            self.setText('[bot]')
        elif y is None:
            self.setText('[???]')
        else:
            self.setText('[{:2}%]'.format(y))

    @pyqtSlot(browsertab.AbstractTab)
    def on_tab_changed(self, tab):
        """Update scroll position when tab changed."""
        self.set_perc(*tab.scroller.pos_perc())
