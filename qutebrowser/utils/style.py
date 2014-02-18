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

from PyQt5.QtWidgets import QCommonStyle, QStyle


class Style(QCommonStyle):

    """Qt style to remove Ubuntu focus rectangle uglyness.

    Unfortunately PyQt doesn't support QProxyStyle, so we need to do this the
    hard way...

    Based on:

    http://stackoverflow.com/a/17294081
    https://code.google.com/p/makehuman/source/browse/trunk/makehuman/lib/qtgui.py # noqa # pylint: disable=line-too-long

    Attributes:
        _style: The base/"parent" style.

    """

    def __init__(self, style):
        """Initialize all functions we're not overriding.

        This simply calls the corresponding function in self._style.

        """
        self._style = style
        for method in ['drawComplexControl', 'drawControl', 'drawItemPixmap',
                       'drawItemText', 'generatedIconPixmap',
                       'hitTestComplexControl', 'itemPixmapRect',
                       'itemTextRect', 'pixelMetric', 'polish', 'styleHint',
                       'subControlRect', 'subElementRect', 'unpolish',
                       'sizeFromContents']:
            target = getattr(self._style, method)
            setattr(self, method, functools.partial(target))
        super().__init__()

    def drawPrimitive(self, element, option, painter, widget=None):
        """Override QCommonStyle.drawPrimitive.

        Call the genuine drawPrimitive of self._style, except when a focus
        rectangle should be drawn.

        """
        if element == QStyle.PE_FrameFocusRect:
            return
        return self._style.drawPrimitive(element, option, painter, widget)
