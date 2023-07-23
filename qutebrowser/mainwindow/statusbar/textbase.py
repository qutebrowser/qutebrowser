# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Base text widgets for statusbar."""

from qutebrowser.qt.core import Qt
from qutebrowser.qt.widgets import QLabel, QSizePolicy
from qutebrowser.qt.gui import QPainter

from qutebrowser.utils import qtutils, utils


class TextBase(QLabel):

    """A text in the statusbar.

    Unlike QLabel, the text will get elided.

    Eliding is loosely based on
    https://gedgedev.blogspot.ch/2010/12/elided-labels-in-qt.html

    Attributes:
        _elidemode: Where to elide the text.
        _elided_text: The current elided text.
    """

    def __init__(self, parent=None, elidemode=Qt.TextElideMode.ElideRight):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._elidemode = elidemode
        self._elided_text = ''

    def __repr__(self):
        return utils.get_repr(self, text=self.text())

    def _update_elided_text(self, width):
        """Update the elided text when necessary.

        Args:
            width: The maximal width the text should take.
        """
        if self.text():
            self._elided_text = self.fontMetrics().elidedText(
                self.text(), self._elidemode, width, Qt.TextFlag.TextShowMnemonic)
        else:
            self._elided_text = ''

    def setText(self, txt):
        """Extend QLabel::setText to update the elided text afterwards.

        Args:
            txt: The text to set (string).
        """
        super().setText(txt)
        if self._elidemode != Qt.TextElideMode.ElideNone:
            self._update_elided_text(self.geometry().width())

    def resizeEvent(self, e):
        """Extend QLabel::resizeEvent to update the elided text afterwards."""
        super().resizeEvent(e)
        size = e.size()
        qtutils.ensure_valid(size)
        self._update_elided_text(size.width())

    def paintEvent(self, e):
        """Override QLabel::paintEvent to draw elided text."""
        if self._elidemode == Qt.TextElideMode.ElideNone:
            super().paintEvent(e)
        else:
            e.accept()
            painter = QPainter(self)
            geom = self.geometry()
            qtutils.ensure_valid(geom)
            painter.drawText(0, 0, geom.width(), geom.height(),
                             int(self.alignment()), self._elided_text)
