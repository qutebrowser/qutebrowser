# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtCore import pyqtSlot, Qt

from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.misc import throttle


class Percentage(textbase.TextBase):

    """Reading percentage displayed in the statusbar."""

    def __init__(self, parent=None):
        """Constructor. Set percentage to 0%."""
        super().__init__(parent, elidemode=Qt.ElideNone)
        self._strings = self._calc_strings()
        self._set_text = throttle.Throttle(self.setText, 100, parent=self)
        self.set_perc(0, 0)

    def set_raw(self):
        self._strings = self._calc_strings(raw=True)

    def _calc_strings(self, raw=False):
        """Pre-calculate strings for the statusbar."""
        fmt = '[{:02}]' if raw else '[{:02}%]'
        strings = {i: fmt.format(i) for i in range(1, 100)}
        strings.update({0: '[top]', 100: '[bot]'})
        return strings

    @pyqtSlot(int, int)
    def set_perc(self, x, y):  # pylint: disable=unused-argument
        """Setter to be used as a Qt slot.

        Args:
            x: The x percentage (int), currently ignored.
            y: The y percentage (int)
        """
        self._set_text(self._strings.get(y, '[???]'))

    def on_tab_changed(self, tab):
        """Update scroll position when tab changed."""
        self.set_perc(*tab.scroller.pos_perc())
