# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Scroll percentage displayed in the statusbar."""

from qutebrowser.qt.core import pyqtSlot, Qt

from qutebrowser.mainwindow.statusbar import textbase
from qutebrowser.misc import throttle
from qutebrowser.utils import utils


class Percentage(textbase.TextBase):

    """Reading percentage displayed in the statusbar."""

    def __init__(self, parent=None):
        """Constructor. Set percentage to 0%."""
        super().__init__(parent, elidemode=Qt.TextElideMode.ElideNone)
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
    def set_perc(self, x, y):
        """Setter to be used as a Qt slot.

        Args:
            x: The x percentage (int), currently ignored.
            y: The y percentage (int)
        """
        utils.unused(x)
        self._set_text(self._strings.get(y, '[???]'))

    def on_tab_changed(self, tab):
        """Update scroll position when tab changed."""
        self.set_perc(*tab.scroller.pos_perc())
