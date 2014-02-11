"""Qt style to remove Ubuntu focus rectangle uglyness.

We might also use this to do more in the future.
"""

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

from PyQt5.QtWidgets import QCommonStyle, QStyle
from PyQt5.QtGui import QPalette

class Style(QCommonStyle):

    """Qt style to remove Ubuntu focus rectangle uglyness.

    Unfortunately PyQt doesn't support QProxyStyle, so we need to do this the
    hard way...

    Based on:

    http://stackoverflow.com/a/17294081
    https://code.google.com/p/makehuman/source/browse/trunk/makehuman/lib/qtgui.py
    """

    def __init__(self, parent):
        self.__parent = parent
        super().__init__()

    def drawComplexControl(self, control, option, painter, widget=None):
        return self.__parent.drawComplexControl(control, option, painter,
                                                widget)

    def drawControl(self, element, option, painter, widget=None):
        return self.__parent.drawControl(element, option, painter, widget)

    def drawItemPixmap(self, painter, rectangle, alignment, pixmap):
        return self.__parent.drawItemPixmap(painter, rectangle, alignment,
                                            pixmap)

    def drawItemText(self, painter, rectangle, alignment, palette, enabled,
                     text, textRole=QPalette.NoRole):
        return self.__parent.drawItemText(painter, rectangle, alignment,
                                          palette, enabled, text, textRole)

    def drawPrimitive(self, element, option, painter, widget=None):
        if (element == QStyle.PE_FrameFocusRect):
            return
        return self.__parent.drawPrimitive(element, option, painter, widget)

    def generatedIconPixmap(self, iconMode, pixmap, option):
        return self.__parent.generatedIconPixmap(iconMode, pixmap, option)

    def hitTestComplexControl(self, control, option, position, widget=None):
        return self.__parent.hitTestComplexControl(control, option, position,
                                                   widget)

    def itemPixmapRect(self, rectangle, alignment, pixmap):
        return self.__parent.itemPixmapRect(rectangle, alignment, pixmap)

    def itemTextRect(self, metrics, rectangle, alignment, enabled, text):
        return self.__parent.itemTextRect(metrics, rectangle, alignment,
                                          enabled, text)

    def pixelMetric(self, metric, option=None, widget=None):
        return self.__parent.pixelMetric(metric, option, widget)

    def polish(self, *args, **kwargs):
        return self.__parent.polish(*args, **kwargs)

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        return self.__parent.styleHint(hint, option, widget, returnData)

    def subControlRect(self, control, option, subControl, widget=None):
        return self.__parent.subControlRect(control, option, subControl,
                                            widget)

    def subElementRect(self, element, option, widget=None):
        return self.__parent.subElementRect(element, option, widget)

    def unpolish(self, *args, **kwargs):
        return self.__parent.unpolish(*args, **kwargs)

    def sizeFromContents(self, ct, opt, contentsSize, widget=None):
        return self.__parent.sizeFromContents(ct, opt, contentsSize, widget)
