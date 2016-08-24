# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Bridge to provide readline-like shortcuts for QLineEdits."""

from PyQt5.QtWidgets import QApplication, QLineEdit

from qutebrowser.commands import cmdutils
from qutebrowser.utils import usertypes as typ
from qutebrowser.utils import utils


class ReadlineBridge:

    """Bridge which provides readline-like commands for the current QLineEdit.

    Attributes:
        _deleted: Mapping from widgets to their last deleted text.
    """

    def __init__(self):
        self._deleted = {}

    def __repr__(self):
        return utils.get_repr(self)

    def _widget(self):
        """Get the currently active QLineEdit."""
        w = QApplication.instance().focusWidget()
        if isinstance(w, QLineEdit):
            return w
        else:
            return None

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_backward_char(self):
        """Move back a character.

        This acts like readline's backward-char.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.cursorBackward(False)

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_forward_char(self):
        """Move forward a character.

        This acts like readline's forward-char.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.cursorForward(False)

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_backward_word(self):
        """Move back to the start of the current or previous word.

        This acts like readline's backward-word.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.cursorWordBackward(False)

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_forward_word(self):
        """Move forward to the end of the next word.

        This acts like readline's forward-word.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.cursorWordForward(False)

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_beginning_of_line(self):
        """Move to the start of the line.

        This acts like readline's beginning-of-line.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.home(False)

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_end_of_line(self):
        """Move to the end of the line.

        This acts like readline's end-of-line.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.end(False)

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_unix_line_discard(self):
        """Remove chars backward from the cursor to the beginning of the line.

        This acts like readline's unix-line-discard.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.home(True)
        self._deleted[widget] = widget.selectedText()
        widget.del_()

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_kill_line(self):
        """Remove chars from the cursor to the end of the line.

        This acts like readline's kill-line.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.end(True)
        self._deleted[widget] = widget.selectedText()
        widget.del_()

    def _rubout(self, delim):
        """Delete backwards using the characters in delim as boundaries."""
        widget = self._widget()
        if widget is None:
            return
        cursor_position = widget.cursorPosition()
        text = widget.text()

        target_position = cursor_position

        is_boundary = True
        while is_boundary and target_position > 0:
            is_boundary = text[target_position - 1] in delim
            target_position -= 1

        is_boundary = False
        while not is_boundary and target_position > 0:
            is_boundary = text[target_position - 1] in delim
            target_position -= 1

        moveby = cursor_position - target_position - 1
        widget.cursorBackward(True, moveby)
        self._deleted[widget] = widget.selectedText()
        widget.del_()

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_unix_word_rubout(self):
        """Remove chars from the cursor to the beginning of the word.

        This acts like readline's unix-word-rubout. Whitespace is used as a
        word delimiter.
        """
        self._rubout([' '])

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_unix_filename_rubout(self):
        """Remove chars from the cursor to the previous path separator.

        This acts like readline's unix-filename-rubout.
        """
        self._rubout([' ', '/'])

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_backward_kill_word(self):
        """Remove chars from the cursor to the beginning of the word.

        This acts like readline's backward-kill-word. Any non-alphanumeric
        character is considered a word delimiter.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.cursorWordBackward(True)
        self._deleted[widget] = widget.selectedText()
        widget.del_()

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_kill_word(self):
        """Remove chars from the cursor to the end of the current word.

        This acts like readline's kill-word.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.cursorWordForward(True)
        self._deleted[widget] = widget.selectedText()
        widget.del_()

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_yank(self):
        """Paste the most recently deleted text.

        This acts like readline's yank.
        """
        widget = self._widget()
        if widget is None or widget not in self._deleted:
            return
        widget.insert(self._deleted[widget])

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_delete_char(self):
        """Delete the character after the cursor.

        This acts like readline's delete-char.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.del_()

    @cmdutils.register(instance='readline-bridge', hide=True,
                       modes=[typ.KeyMode.command, typ.KeyMode.prompt])
    def rl_backward_delete_char(self):
        """Delete the character before the cursor.

        This acts like readline's backward-delete-char.
        """
        widget = self._widget()
        if widget is None:
            return
        widget.backspace()
