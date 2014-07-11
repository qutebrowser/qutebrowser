# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Qt style to remove Ubuntu focus rectangle uglyness.

We might also use this to do more in the future.
"""

import functools

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QCommonStyle, QStyle


class Style(QCommonStyle):

    """Qt style to remove Ubuntu focus rectangle uglyness.

    Unfortunately PyQt doesn't support QProxyStyle, so we need to do this the
    hard way...

    Based on:

    http://stackoverflow.com/a/17294081
    https://code.google.com/p/makehuman/source/browse/trunk/makehuman/lib/qtgui.py

    Attributes:
        _style: The base/"parent" style.
    """

    def __init__(self, style):
        """Initialize all functions we're not overriding.

        This simply calls the corresponding function in self._style.

        Args:
            style: The base/"parent" style.
        """
        self._style = style
        for method in ('drawComplexControl', 'drawControl', 'drawItemPixmap',
                       'generatedIconPixmap', 'hitTestComplexControl',
                       'itemPixmapRect', 'itemTextRect', 'pixelMetric',
                       'polish', 'styleHint', 'subControlRect',
                       'subElementRect', 'unpolish', 'sizeFromContents'):
            target = getattr(self._style, method)
            setattr(self, method, functools.partial(target))
        super().__init__()

    def drawPrimitive(self, element, option, painter, widget=None):
        """Override QCommonStyle.drawPrimitive.

        Call the genuine drawPrimitive of self._style, except when a focus
        rectangle should be drawn.

        Args:
            element: PrimitiveElement pe
            option: const QStyleOption * opt
            painter: QPainter * p
            widget: const QWidget * widget
        """
        if element == QStyle.PE_FrameFocusRect:
            return
        return self._style.drawPrimitive(element, option, painter, widget)

    def drawItemText(self, painter, rectangle, alignment, palette, enabled,
                     text, textRole=QPalette.NoRole):
        """Extend QCommonStyle::drawItemText to not center-align text.

        Since Qt hardcodes the text alignment for tabbar tabs in QCommonStyle,
        we need to undo this here by deleting the flag again, and align left
        instead.


        Draws the given text in the specified rectangle using the provided
        painter and palette.

        The text is drawn using the painter's pen, and aligned and wrapped
        according to the specified alignment. If an explicit textRole is
        specified, the text is drawn using the palette's color for the given
        role. The enabled parameter indicates whether or not the item is
        enabled; when reimplementing this function, the enabled parameter
        should influence how the item is drawn.

        Args:
            painter: QPainter *
            rectangle: const QRect &
            alignment int (Qt::Alignment)
            palette: const QPalette &
            enabled: bool
            text: const QString &
            textRole: QPalette::ColorRole textRole
        """
        alignment &=~ Qt.AlignHCenter
        alignment |= Qt.AlignLeft
        super().drawItemText(painter, rectangle, alignment, palette, enabled,
                             text, textRole)
