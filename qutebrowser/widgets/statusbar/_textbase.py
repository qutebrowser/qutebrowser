# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Base text widgets for statusbar."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QSizePolicy
from PyQt5.QtGui import QPainter


class TextBase(QLabel):

    """A text in the statusbar.

    Unlike QLabel, the text will get elided.

    Eliding is loosly based on
    http://gedgedev.blogspot.ch/2010/12/elided-labels-in-qt.html

    Attributes:
        _elidemode: Where to elide the text.
        _elided_text: The current elided text.
    """

    def __init__(self, bar, elidemode=Qt.ElideRight):
        super().__init__(bar)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._elidemode = elidemode
        self._elided_text = ''

    def _update_elided_text(self, width):
        """Update the elided text when necessary.

        Args:
            width: The maximal width the text should take.
        """
        self._elided_text = self.fontMetrics().elidedText(
            self.text(), self._elidemode, width, Qt.TextShowMnemonic)

    def setText(self, txt):
        """Extend QLabel::setText.

        This update the elided text after setting the text, and also works
        around a weird QLabel redrawing bug where it doesn't redraw correctly
        when the text is empty -- we explicitely need to call repaint() to
        resolve this. See http://stackoverflow.com/q/21890462/2085149

        Args:
            txt: The text to set (string).
        """
        super().setText(txt)
        self._update_elided_text(self.geometry().width())
        if not txt:
            self.repaint()

    def resizeEvent(self, e):
        """Extend QLabel::resizeEvent to update the elided text afterwards."""
        super().resizeEvent(e)
        self._update_elided_text(e.size().width())

    def paintEvent(self, e):
        """Override QLabel::paintEvent to draw elided text."""
        if self._elidemode == Qt.ElideNone:
            super().paintEvent(e)
        else:
            painter = QPainter(self)
            painter.drawText(0, 0, self.geometry().width(),
                             self.geometry().height(), self.alignment(),
                             self._elided_text)
