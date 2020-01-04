# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import typing

from PyQt5.QtWidgets import QApplication, QLineEdit

from qutebrowser.api import cmdutils


class _ReadlineBridge:

    """Bridge which provides readline-like commands for the current QLineEdit.

    Attributes:
        _deleted: Mapping from widgets to their last deleted text.
    """

    def __init__(self) -> None:
        self._deleted = {}  # type: typing.MutableMapping[QLineEdit, str]

    def _widget(self) -> typing.Optional[QLineEdit]:
        """Get the currently active QLineEdit."""
        w = QApplication.instance().focusWidget()
        if isinstance(w, QLineEdit):
            return w
        else:
            return None

    def _dispatch(self, name: str, *,
                  mark: bool = None,
                  delete: bool = False) -> None:
        widget = self._widget()
        if widget is None:
            return

        method = getattr(widget, name)
        if mark is None:
            method()
        else:
            method(mark)

        if delete:
            self._deleted[widget] = widget.selectedText()
            widget.del_()

    def backward_char(self) -> None:
        self._dispatch('cursorBackward', mark=False)

    def forward_char(self) -> None:
        self._dispatch('cursorForward', mark=False)

    def backward_word(self) -> None:
        self._dispatch('cursorWordBackward', mark=False)

    def forward_word(self) -> None:
        self._dispatch('cursorWordForward', mark=False)

    def beginning_of_line(self) -> None:
        self._dispatch('home', mark=False)

    def end_of_line(self) -> None:
        self._dispatch('end', mark=False)

    def unix_line_discard(self) -> None:
        self._dispatch('home', mark=True, delete=True)

    def kill_line(self) -> None:
        self._dispatch('end', mark=True, delete=True)

    def _rubout(self, delim: typing.Iterable[str]) -> None:
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

    def unix_word_rubout(self) -> None:
        self._rubout([' '])

    def unix_filename_rubout(self) -> None:
        self._rubout([' ', '/'])

    def backward_kill_word(self) -> None:
        self._dispatch('cursorWordBackward', mark=True, delete=True)

    def kill_word(self) -> None:
        self._dispatch('cursorWordForward', mark=True, delete=True)

    def yank(self) -> None:
        """Paste previously deleted text."""
        widget = self._widget()
        if widget is None or widget not in self._deleted:
            return
        widget.insert(self._deleted[widget])

    def delete_char(self) -> None:
        self._dispatch('del_')

    def backward_delete_char(self) -> None:
        self._dispatch('backspace')


bridge = _ReadlineBridge()
_register = cmdutils.register(
    modes=[cmdutils.KeyMode.command, cmdutils.KeyMode.prompt])


@_register
def rl_backward_char() -> None:
    """Move back a character.

    This acts like readline's backward-char.
    """
    bridge.backward_char()


@_register
def rl_forward_char() -> None:
    """Move forward a character.

    This acts like readline's forward-char.
    """
    bridge.forward_char()


@_register
def rl_backward_word() -> None:
    """Move back to the start of the current or previous word.

    This acts like readline's backward-word.
    """
    bridge.backward_word()


@_register
def rl_forward_word() -> None:
    """Move forward to the end of the next word.

    This acts like readline's forward-word.
    """
    bridge.forward_word()


@_register
def rl_beginning_of_line() -> None:
    """Move to the start of the line.

    This acts like readline's beginning-of-line.
    """
    bridge.beginning_of_line()


@_register
def rl_end_of_line() -> None:
    """Move to the end of the line.

    This acts like readline's end-of-line.
    """
    bridge.end_of_line()


@_register
def rl_unix_line_discard() -> None:
    """Remove chars backward from the cursor to the beginning of the line.

    This acts like readline's unix-line-discard.
    """
    bridge.unix_line_discard()


@_register
def rl_kill_line() -> None:
    """Remove chars from the cursor to the end of the line.

    This acts like readline's kill-line.
    """
    bridge.kill_line()


@_register
def rl_unix_word_rubout() -> None:
    """Remove chars from the cursor to the beginning of the word.

    This acts like readline's unix-word-rubout. Whitespace is used as a
    word delimiter.
    """
    bridge.unix_word_rubout()


@_register
def rl_unix_filename_rubout() -> None:
    """Remove chars from the cursor to the previous path separator.

    This acts like readline's unix-filename-rubout.
    """
    bridge.unix_filename_rubout()


@_register
def rl_backward_kill_word() -> None:
    """Remove chars from the cursor to the beginning of the word.

    This acts like readline's backward-kill-word. Any non-alphanumeric
    character is considered a word delimiter.
    """
    bridge.backward_kill_word()


@_register
def rl_kill_word() -> None:
    """Remove chars from the cursor to the end of the current word.

    This acts like readline's kill-word.
    """
    bridge.kill_word()


@_register
def rl_yank() -> None:
    """Paste the most recently deleted text.

    This acts like readline's yank.
    """
    bridge.yank()


@_register
def rl_delete_char() -> None:
    """Delete the character after the cursor.

    This acts like readline's delete-char.
    """
    bridge.delete_char()


@_register
def rl_backward_delete_char() -> None:
    """Delete the character before the cursor.

    This acts like readline's backward-delete-char.
    """
    bridge.backward_delete_char()
