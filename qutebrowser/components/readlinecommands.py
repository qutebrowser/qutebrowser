# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Bridge to provide readline-like shortcuts for QLineEdits."""

import os
from typing import Iterable, Optional, MutableMapping, Any, Callable

from PyQt5.QtWidgets import QApplication, QLineEdit

from qutebrowser.api import cmdutils


class _ReadlineBridge:

    """Bridge which provides readline-like commands for the current QLineEdit.

    Attributes:
        _deleted: Mapping from widgets to their last deleted text.
    """

    def __init__(self) -> None:
        self._deleted: MutableMapping[QLineEdit, str] = {}

    def _widget(self) -> Optional[QLineEdit]:
        """Get the currently active QLineEdit."""
        # FIXME add this to api.utils or so
        qapp = QApplication.instance()
        assert qapp is not None
        w = qapp.focusWidget()

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

    def rubout(self, delim: Iterable[str]) -> None:
        """Delete backwards using the characters in delim as boundaries.

        With delim=[' '], this acts like unix-word-rubout.
        With delim=[' ', '/'], this acts like unix-filename-rubout.
        With delim=[os.sep], this serves as a more useful filename-rubout.
        """
        widget = self._widget()
        if widget is None:
            return
        cursor_position = widget.cursorPosition()
        text = widget.text()

        target_position = cursor_position

        # First scan any trailing boundaries, e.g.:
        # /some/path//|        ->        /some/path[//]
        # 0           ^ 12               0        ^ 9
        #             (cursor)                    (target)
        is_boundary = True
        while is_boundary and target_position > 0:
            is_boundary = text[target_position - 1] in delim
            target_position -= 1

        # Then scan anything not a boundary, e.g.
        # /some/path         ->        /some/[path//]
        # 0        ^ 9                 0    ^ 5
        #          (old target)             (target)
        is_boundary = False
        while not is_boundary and target_position > 0:
            is_boundary = text[target_position - 1] in delim
            target_position -= 1

        # Account for the last remaining character.
        # With e.g.:
        #
        # somepath|
        # 0       8
        #
        # We exit the loop above with cursor_position=8 and target_position=0.
        # However, we want to *keep* the found boundary usually, thus only
        # trying to delete 7 chars:
        #
        # s[omepath]
        #
        # However, that would be wrong: We also want to remove the *initial*
        # character, if it was not a boundary.
        # We can't say "target_position >= 0" above, because that'd falsely
        # check whether text[-1] was a boundary.
        if not is_boundary:
            # target_position can never be negative, and if it's > 0, then the
            # loop above could only have exited because of is_boundary=True,
            # thus we can only end up here if target_position=0.
            assert target_position == 0, (text, delim)
            target_position -= 1

        # Finally, move back as calculated - in the example above:
        #
        #        vvvvvv---- 12 - 5 - 1 = 6 chars to delete.
        # /some/[path//]|
        #      ^ 5      ^ 12
        #      (target) (cursor)
        #
        # If we have a text without an initial boundary:
        #
        #   vvvvvvvv---- 8 - (-1) - 1 = 8 chars to delete.
        #  [somepath]|
        # ^ -1       ^ 8
        # (target)   (cursor)
        moveby = cursor_position - target_position - 1
        widget.cursorBackward(True, moveby)
        self._deleted[widget] = widget.selectedText()
        widget.del_()

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


def _register(**kwargs: Any) -> Callable[..., Any]:
    return cmdutils.register(
        modes=[cmdutils.KeyMode.command, cmdutils.KeyMode.prompt],
        **kwargs)


@_register()
def rl_backward_char() -> None:
    """Move back a character.

    This acts like readline's backward-char.
    """
    bridge.backward_char()


@_register()
def rl_forward_char() -> None:
    """Move forward a character.

    This acts like readline's forward-char.
    """
    bridge.forward_char()


@_register()
def rl_backward_word() -> None:
    """Move back to the start of the current or previous word.

    This acts like readline's backward-word.
    """
    bridge.backward_word()


@_register()
def rl_forward_word() -> None:
    """Move forward to the end of the next word.

    This acts like readline's forward-word.
    """
    bridge.forward_word()


@_register()
def rl_beginning_of_line() -> None:
    """Move to the start of the line.

    This acts like readline's beginning-of-line.
    """
    bridge.beginning_of_line()


@_register()
def rl_end_of_line() -> None:
    """Move to the end of the line.

    This acts like readline's end-of-line.
    """
    bridge.end_of_line()


@_register()
def rl_unix_line_discard() -> None:
    """Remove chars backward from the cursor to the beginning of the line.

    This acts like readline's unix-line-discard.
    """
    bridge.unix_line_discard()


@_register()
def rl_kill_line() -> None:
    """Remove chars from the cursor to the end of the line.

    This acts like readline's kill-line.
    """
    bridge.kill_line()


@_register(deprecated="Use :rl-rubout ' ' instead.")
def rl_unix_word_rubout() -> None:
    """Remove chars from the cursor to the beginning of the word.

    This acts like readline's unix-word-rubout. Whitespace is used as a
    word delimiter.
    """
    bridge.rubout([" "])


@_register(
    deprecated='Use :rl-filename-rubout or :rl-rubout " /" instead '
               '(see their `:help` for details).'
)
def rl_unix_filename_rubout() -> None:
    """Remove chars from the cursor to the previous path separator.

    This acts like readline's unix-filename-rubout.
    """
    bridge.rubout([" ", "/"])


@_register()
def rl_rubout(delim: str) -> None:
    r"""Delete backwards using the given characters as boundaries.

    With " ", this acts like readline's `unix-word-rubout`.

    With " /", this acts like readline's `unix-filename-rubout`, but consider
    using `:rl-filename-rubout` instead: It uses the OS path separator (i.e. `\`
    on Windows) and ignores spaces.

    Args:
        delim: A string of characters (or a single character) until which text
               will be deleted.
    """
    bridge.rubout(list(delim))


@_register()
def rl_filename_rubout() -> None:
    r"""Delete backwards using the OS path separator as boundary.

    For behavior that matches readline's `unix-filename-rubout` exactly, use
    `:rl-rubout "/ "` instead. This command uses the OS path separator (i.e.
    `\` on Windows) and ignores spaces.
    """
    bridge.rubout(os.sep)


@_register()
def rl_backward_kill_word() -> None:
    """Remove chars from the cursor to the beginning of the word.

    This acts like readline's backward-kill-word. Any non-alphanumeric
    character is considered a word delimiter.
    """
    bridge.backward_kill_word()


@_register()
def rl_kill_word() -> None:
    """Remove chars from the cursor to the end of the current word.

    This acts like readline's kill-word.
    """
    bridge.kill_word()


@_register()
def rl_yank() -> None:
    """Paste the most recently deleted text.

    This acts like readline's yank.
    """
    bridge.yank()


@_register()
def rl_delete_char() -> None:
    """Delete the character after the cursor.

    This acts like readline's delete-char.
    """
    bridge.delete_char()


@_register()
def rl_backward_delete_char() -> None:
    """Delete the character before the cursor.

    This acts like readline's backward-delete-char.
    """
    bridge.backward_delete_char()
