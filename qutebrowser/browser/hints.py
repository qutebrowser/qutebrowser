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

import logging
import math
from collections import namedtuple

from PyQt5.QtCore import pyqtSignal, QObject, QEvent, Qt
from PyQt5.QtGui import QMouseEvent

import qutebrowser.config.config as config
from qutebrowser.utils.keyparser import KeyParser


ElemTuple = namedtuple('ElemTuple', 'elem, label')


class HintKeyParser(KeyParser):

    """KeyParser for hints.

    Class attributes:
        supports_count: If the keyparser should support counts.

    Signals:
        fire_hint: When a hint keybinding was completed.
                   Arg: the keystring/hint string pressed.
        abort_hinting: Esc pressed, so abort hinting.
    """

    supports_count = False
    fire_hint = pyqtSignal(str)
    abort_hinting = pyqtSignal()

    def _handle_modifier_key(self, e):
        """We don't support modifiers here, but we'll handle escape in here."""
        if e.key() == Qt.Key_Escape:
            self._keystring = ''
            self.abort_hinting.emit()
            return True
        return False

    def execute(self, cmdstr, count=None):
        """Handle a completed keychain."""
        self.fire_hint.emit(cmdstr)

    def on_hint_strings_updated(self, strings):
        """Handler for HintManager's hint_strings_updated.

        Args:
            strings: A list of hint strings.
        """
        self.bindings = {s: s for s in strings}


class HintManager(QObject):

    """Manage drawing hints over links or other elements.

    Class attributes:
        SELECTORS: CSS selectors for the different highlighting modes.
        HINT_CSS: The CSS template to use for hints.

    Attributes:
        _frame: The QWebFrame to use.
        _elems: A mapping from keystrings to (elem, label) namedtuples.

    Signals:
        hint_strings_updated: Emitted when the possible hint strings changed.
                              arg: A list of hint strings.
        set_mode: Emitted when the input mode should be changed.
                  arg: The new mode, as a string.
        mouse_event: Mouse event to be posted in the web view.
                     arg: A QMouseEvent
        openurl: Open a new url
                 arg 0: URL to open as a string.
                 arg 1: true if it should be opened in a new tab, else false.
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
        color: {config[colors][hints.fg]};
        background: {config[colors][hints.bg]};
        font: {config[fonts][hints]};
        border: {config[hints][border]};
        opacity: {config[hints][opacity]};
        z-index: 100000;
        position: absolute;
        left: {left}px;
        top: {top}px;
    """

    hint_strings_updated = pyqtSignal(list)
    set_mode = pyqtSignal(str)
    mouse_event = pyqtSignal('QMouseEvent')

    def __init__(self, frame):
        """Constructor.

        Args:
            frame: The QWebFrame to use for finding elements and drawing.
        """
        super().__init__(frame)
        self._frame = frame
        self._elems = {}

    def _hint_strings(self, elems):
        """Calculate the hint strings for elems.

        Inspirated by Vimium.

        Args:
            elems: The elements to get hint strings for.

        Return:
            A list of hint strings, in the same order as the elements.
        """
        chars = config.get("hints", "chars")
        # Determine how many digits the link hints will require in the worst
        # case. Usually we do not need all of these digits for every link
        # single hint, so we can show shorter hints for a few of the links.
        needed = math.ceil(math.log(len(elems), len(chars)))
        # Short hints are the number of hints we can possibly show which are
        # (needed - 1) digits in length.
        short_count = math.floor((len(chars) ** needed - len(elems)) /
                                 len(chars))
        long_count = len(elems) - short_count

        strings = []

        if needed > 1:
            for i in range(short_count):
                strings.append(self._number_to_hint_str(i, chars, needed - 1))

        start = short_count * len(chars)
        for i in range(start, start + long_count):
            strings.append(self._number_to_hint_str(i, chars, needed))

        return self._shuffle_hints(strings, len(chars))

    def _shuffle_hints(self, hints, length):
        """Shuffle the given set of hints so that they're scattered.

        Hints starting with the same character will be spread evenly throughout
        the array.

        Inspired by Vimium.

        Args:
            hints: A list of hint strings.
            length: Length of the available charset.

        Return:
            A list of shuffled hint strings.
        """
        buckets = [[] for i in range(length)]
        for i, hint in enumerate(hints):
            buckets[i % len(buckets)].append(hint)
        result = []
        for bucket in buckets:
            result += bucket
        return result

    def _number_to_hint_str(self, number, chars, digits=0):
        """Convert a number like "8" into a hint string like "JK".

        This is used to sequentially generate all of the hint text.
        The hint string will be "padded with zeroes" to ensure its length is >=
        digits.

        Inspired by Vimium.

        Args:
            number: The hint number.
            chars: The charset to use.
            digits: The minimum output length.

        Return:
            A hint string.
        """
        base = len(chars)
        hintstr = []
        remainder = 0
        while True:
            remainder = number % base
            hintstr.insert(0, chars[remainder])
            number -= remainder
            number //= base
            if number <= 0:
                break
        # Pad the hint string we're returning so that it matches digits.
        for _ in range(0, digits - len(hintstr)):
            hintstr.insert(0, chars[0])
        return ''.join(hintstr)

    def _draw_label(self, elem, string):
        """Draw a hint label over an element.

        Args:
            elem: The QWebElement to use.
            string: The hint string to print.

        Return:
            The newly created label elment
        """
        rect = elem.geometry()
        css = HintManager.HINT_CSS.format(left=rect.x(), top=rect.y(),
                                          config=config.instance)
        doc = self._frame.documentElement()
        doc.appendInside('<span class="qutehint" style="{}">{}</span>'.format(
            css, string))
        return doc.lastChild()

    def start(self, mode="all"):
        """Start hinting.

        Args:
            mode: The mode to be used.
        """
        selector = HintManager.SELECTORS[mode]
        elems = self._frame.findAllElements(selector)
        visible_elems = []
        for e in elems:
            rect = e.geometry()
            if (not rect.isValid()) and rect.x() == 0:
                # Most likely an invisible link
                continue
            framegeom = self._frame.geometry()
            framegeom.translate(self._frame.scrollPosition())
            if not framegeom.contains(rect.topLeft()):
                # out of screen
                continue
            visible_elems.append(e)
        strings = self._hint_strings(visible_elems)
        for e, string in zip(visible_elems, strings):
            label = self._draw_label(e, string)
            self._elems[string] = ElemTuple(e, label)
        self.hint_strings_updated.emit(strings)
        self.set_mode.emit("hint")

    def stop(self):
        """Stop hinting."""
        for elem in self._elems.values():
            elem.label.removeFromDocument()
        self._elems = {}
        self.set_mode.emit("normal")

    def handle_partial_key(self, keystr):
        """Handle a new partial keypress."""
        delete = []
        for (string, elems) in self._elems.items():
            if string.startswith(keystr):
                matched = string[:len(keystr)]
                rest = string[len(keystr):]
                elems.label.setInnerXml('<font color="{}">{}</font>{}'.format(
                    config.get("colors", "hints.fg.match"), matched, rest))
            else:
                elems.label.removeFromDocument()
                delete.append(string)
        for key in delete:
            del self._elems[key]

    def fire(self, keystr):
        """Fire a completed hint."""
        elem = self._elems[keystr].elem
        logging.debug("Clicking on: {}".format(elem.toPlainText()))
        self.stop()
        events = [
            QMouseEvent(QEvent.MouseMove, elem.geometry().topLeft(),
                        Qt.NoButton, Qt.NoButton, Qt.NoModifier),
            QMouseEvent(QEvent.MouseButtonPress, elem.geometry().topLeft(),
                        Qt.LeftButton, Qt.NoButton, Qt.NoModifier),
            QMouseEvent(QEvent.MouseButtonRelease, elem.geometry().topLeft(),
                        Qt.LeftButton, Qt.NoButton, Qt.NoModifier),
        ]
        for evt in events:
            self.mouse_event.emit(evt)
