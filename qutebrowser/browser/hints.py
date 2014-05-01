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

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QEvent, Qt
from PyQt5.QtGui import QMouseEvent, QClipboard
from PyQt5.QtWidgets import QApplication

import qutebrowser.config.config as config
import qutebrowser.keyinput.modeman as modeman
import qutebrowser.utils.message as message
import qutebrowser.utils.url as urlutils
import qutebrowser.utils.webelem as webelem


ElemTuple = namedtuple('ElemTuple', 'elem, label')


class HintManager(QObject):

    """Manage drawing hints over links or other elements.

    Class attributes:
        HINT_CSS: The CSS template to use for hints.

    Attributes:
        _frame: The QWebFrame to use.
        _elems: A mapping from keystrings to (elem, label) namedtuples.
        _baseurl: The URL of the current page.
        _target: What to do with the opened links.
                 'normal'/'tab'/'bgtab': Get passed to BrowserTab.
                 'yank'/'yank_primary': Yank to clipboard/primary selection
                 'cmd'/'cmd_tab'/'cmd_bgtab': Enter link to commandline
                 'rapid': Rapid mode with background tabs
        _to_follow: The link to follow when enter is pressed.

    Signals:
        hint_strings_updated: Emitted when the possible hint strings changed.
                              arg: A list of hint strings.
        mouse_event: Mouse event to be posted in the web view.
                     arg: A QMouseEvent
        openurl: Open a new url
                 arg 0: URL to open as QUrl.
                 arg 1: True if it should be opened in a new tab, else False.
        set_open_target: Set a new target to open the links in.
    """

    HINT_CSS = """
        color: {config[colors][hints.fg]};
        background: {config[colors][hints.bg]};
        font: {config[fonts][hints]};
        border: {config[hints][border]};
        opacity: {config[hints][opacity]};
        z-index: 100000;
        pointer-events: none;
        position: absolute;
        left: {left}px;
        top: {top}px;
    """

    hint_strings_updated = pyqtSignal(list)
    mouse_event = pyqtSignal('QMouseEvent')
    openurl = pyqtSignal('QUrl', bool)
    set_open_target = pyqtSignal(str)

    def __init__(self, parent=None):
        """Constructor.

        Args:
            frame: The QWebFrame to use for finding elements and drawing.
        """
        super().__init__(parent)
        self._elems = {}
        self._frame = None
        self._target = None
        self._baseurl = None
        self._to_follow = None
        modeman.manager.left.connect(self.on_mode_left)

    def _hint_strings(self, elems):
        """Calculate the hint strings for elems.

        Inspired by Vimium.

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
        css = self.HINT_CSS.format(left=rect.x(), top=rect.y(),
                                   config=config.instance)
        doc = self._frame.documentElement()
        # It seems impossible to create an empty QWebElement for which isNull()
        # is false so we can work with it.
        # As a workaround, we use appendInside() with markup as argument, and
        # then use lastChild() to get a reference to it.
        # See: http://stackoverflow.com/q/7364852/2085149
        doc.appendInside('<span class="qutehint" style="{}">{}</span>'.format(
                         css, string))
        return doc.lastChild()

    def _click(self, elem):
        """Click an element.

        Args:
            elem: The QWebElement to click.
        """
        if self._target == 'rapid':
            target = 'bgtab'
        else:
            target = self._target
        self.set_open_target.emit(target)
        point = elem.geometry().topLeft()
        scrollpos = self._frame.scrollPosition()
        logging.debug("Clicking on \"{}\" at {}/{} - {}/{}".format(
            elem.toPlainText(), point.x(), point.y(), scrollpos.x(),
            scrollpos.y()))
        point -= scrollpos
        events = [
            QMouseEvent(QEvent.MouseMove, point, Qt.NoButton, Qt.NoButton,
                        Qt.NoModifier),
            QMouseEvent(QEvent.MouseButtonPress, point, Qt.LeftButton,
                        Qt.NoButton, Qt.NoModifier),
            QMouseEvent(QEvent.MouseButtonRelease, point, Qt.LeftButton,
                        Qt.NoButton, Qt.NoModifier),
        ]
        for evt in events:
            self.mouse_event.emit(evt)

    def _yank(self, link):
        """Yank an element to the clipboard or primary selection.

        Args:
            link: The URL to open.
        """
        sel = self._target == 'yank_primary'
        mode = QClipboard.Selection if sel else QClipboard.Clipboard
        QApplication.clipboard().setText(urlutils.urlstring(link), mode)
        message.info("URL yanked to {}".format("primary selection" if sel
                                               else "clipboard"))

    def _preset_cmd_text(self, link):
        """Preset a commandline text based on a hint URL.

        Args:
            link: The link to open.
        """
        commands = {
            'cmd': 'open',
            'cmd_tab': 'tabopen',
            'cmd_bgtab': 'backtabopen',
        }
        message.set_cmd_text(':{} {}'.format(commands[self._target],
                                             urlutils.urlstring(link)))

    def _resolve_link(self, elem):
        """Resolve a link and check if we want to keep it.

        Args:
            elem: The QWebElement to get the link of.

        Return:
            A QUrl with the absolute link, or None.
        """
        link = elem.attribute('href')
        if not link:
            return None
        link = urlutils.qurl(link)
        if link.isRelative():
            link = self._baseurl.resolved(link)
        return link

    def _find_prevnext(self, frame, prev=False):
        """Find a prev/next element in frame."""
        # First check for <link rel="prev(ious)|next">
        elems = frame.findAllElements(webelem.SELECTORS['prevnext_rel'])
        rel_values = ['prev', 'previous'] if prev else ['next']
        for e in elems:
            if e.attribute('rel') in rel_values:
                return e
        # Then check for regular links
        elems = frame.findAllElements(webelem.SELECTORS['prevnext'])
        option = 'prev-regexes' if prev else 'next-regexes'
        if not elems:
            return None
        for regex in config.get('hints', option):
            for e in elems:
                if regex.match(e.toPlainText()):
                    return e
        return None

    def follow_prevnext(self, frame, prev=False, newtab=False):
        """Click a "previous"/"next" element on the page.

        Args:
            frame: The frame where the element is in.
            prev: True to open a "previous" link, False to open a "next" link.
            newtab: True to open in a new tab, False for the current tab.
        """
        elem = self._find_prevnext(frame, prev)
        if elem is None:
            message.error("No {} links found!".format("prev" if prev
                                                      else "forward"))
            return
        link = self._resolve_link(elem)
        if link is None:
            message.error("No {} links found!".format("prev" if prev
                                                      else "forward"))
            return
        self.openurl.emit(link, newtab)


    def start(self, frame, baseurl, mode='all', target='normal'):
        """Start hinting.

        Args:
            frame: The QWebFrame to place hints in.
            baseurl: URL of the current page.
            mode: The mode to be used.
            target: What to do with the link. See attribute docstring.

        Emit:
            hint_strings_updated: Emitted to update keypraser.
        """
        self._target = target
        self._baseurl = baseurl
        self._frame = frame
        elems = frame.findAllElements(webelem.SELECTORS[mode])
        filterfunc = webelem.FILTERS.get(mode, lambda e: True)
        visible_elems = []
        for e in elems:
            if filterfunc(e) and webelem.is_visible(e, self._frame):
                visible_elems.append(e)
        if not visible_elems:
            message.error("No elements found.")
            return
        texts = {
            'normal': "Follow hint...",
            'tab': "Follow hint in new tab...",
            'bgtab': "Follow hint in background tab...",
            'yank': "Yank hint to clipboard...",
            'yank_primary': "Yank hint to primary selection...",
            'cmd': "Set hint in commandline...",
            'cmd_tab': "Set hint in commandline as new tab...",
            'cmd_bgtab': "Set hint in commandline as background tab...",
            'rapid': "Follow hint (rapid mode)...",
        }
        message.text(texts[target])
        strings = self._hint_strings(visible_elems)
        for e, string in zip(visible_elems, strings):
            label = self._draw_label(e, string)
            self._elems[string] = ElemTuple(e, label)
        frame.contentsSizeChanged.connect(self.on_contents_size_changed)
        self.hint_strings_updated.emit(strings)
        modeman.enter('hint')

    def handle_partial_key(self, keystr):
        """Handle a new partial keypress."""
        delete = []
        for (string, elems) in self._elems.items():
            if string.startswith(keystr):
                matched = string[:len(keystr)]
                rest = string[len(keystr):]
                elems.label.setInnerXml('<font color="{}">{}</font>{}'.format(
                    config.get('colors', 'hints.fg.match'), matched, rest))
            else:
                elems.label.removeFromDocument()
                delete.append(string)
        for key in delete:
            del self._elems[key]

    def fire(self, keystr, force=False):
        """Fire a completed hint.

        Args:
            keystr: The keychain string to follow.
            force: When True, follow even when auto-follow is false.
        """
        if not (force or config.get('hints', 'auto-follow')):
            self.handle_partial_key(keystr)
            self._to_follow = keystr
            return
        # Handlers which take a QWebElement
        elem_handlers = {
            'normal': self._click,
            'tab': self._click,
            'bgtab': self._click,
            'rapid': self._click,
        }
        # Handlers which take a link string
        link_handlers = {
            'yank': self._yank,
            'yank_primary': self._yank,
            'cmd': self._preset_cmd_text,
            'cmd_tab': self._preset_cmd_text,
            'cmd_bgtab': self._preset_cmd_text,
        }
        elem = self._elems[keystr].elem
        if self._target in elem_handlers:
            elem_handlers[self._target](elem)
        elif self._target in link_handlers:
            link = self._resolve_link(elem)
            if link is None:
                message.error("No suitable link found for this element.")
                return
            link_handlers[self._target](link)
        if self._target != 'rapid':
            modeman.leave('hint')

    def follow_hint(self):
        """Follow the currently selected hint."""
        if not self._to_follow:
            message.error("No hint to follow")
        self.fire(self._to_follow, force=True)

    @pyqtSlot('QSize')
    def on_contents_size_changed(self, _size):
        """Reposition hints if contents size changed."""
        for elems in self._elems.values():
            rect = elems.elem.geometry()
            css = self.HINT_CSS.format(left=rect.x(), top=rect.y(),
                                       config=config.instance)
            elems.label.setAttribute('style', css)

    @pyqtSlot(str)
    def on_mode_left(self, mode):
        """Stop hinting when hinting mode was left."""
        if mode != 'hint':
            return
        for elem in self._elems.values():
            elem.label.removeFromDocument()
        self._frame.contentsSizeChanged.disconnect(
            self.on_contents_size_changed)
        self._elems = {}
        self._to_follow = None
        self._target = None
        self._frame = None
        message.clear()
