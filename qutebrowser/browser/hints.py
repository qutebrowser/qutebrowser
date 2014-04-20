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

"""A HintManager to draw hints over links."""


class HintManager:

    """Manage drawing hints over links or other elements.

    Class attributes:
        SELECTORS: CSS selectors for the different highlighting modes.

    Attributes:
        _frame: The QWebFrame to use.
        _elems: The elements we're hinting currently.
    """

    SELECTORS = {
        "all": ("a, textarea, select, input:not([type=hidden]), button, "
                "frame, iframe, [onclick], [onmousedown], [role=link], "
                "[role=option], [role=button], img"),
        "links": "a",
        "images": "img",
        # FIXME remove input:not([type=hidden]) and add mor explicit inputs.
        "editable": ("input:not([type=hidden]), input[type=text], "
                     "input[type=password], input[type=search], textarea"),
        "url": "[src], [href]",
    }

    HINT_CSS = """
        background: -webkit-gradient(linear, left top, left bottom,
                    color-stop(0%,#FFF785), color-stop(100%,#FFC542));
        border: 1px solid #E3BE23;
        opacity: 0.7;
        color: black;
        font-weight: bold;
        font-family: monospace;
        font-size: 12px;
        z-index: 100000;
        position: absolute;
        left: {left}px;
        top: {top}px;
    """

    def __init__(self, frame):
        """Constructor.

        Args:
            frame: The QWebFrame to use for finding elements and drawing.
        """
        self._frame = frame
        self._elems = None

    def _draw_label(self, elem):
        """Draw a hint label over an element."""
        rect = elem.geometry()
        css = HintManager.HINT_CSS.format(left=rect.x(), top=rect.y())
        self._frame.documentElement().appendInside(
            '<span class="qutehint" style="{}">foo</span>'.format(css))

    def start(self, mode="all"):
        """Start hinting.

        Args:
            mode: The mode to be used.
        """
        selector = HintManager.SELECTORS[mode]
        self._elems = self._frame.findAllElements(selector)
        for e in self._elems:
            self._draw_label(e)

    def stop(self):
        """Stop hinting."""
        self._elems = None
        for e in self._frame.findAllElements("span.qutehint"):
            e.removeFromDocument()
