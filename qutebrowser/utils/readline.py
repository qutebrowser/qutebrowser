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

"""Bridge to provide readline-like shortcuts for QLineEdits."""

from PyQt5.QtWidgets import QApplication, QLineEdit

import qutebrowser.commands.utils as cmd
from qutebrowser.utils.usertypes import KeyMode


class ReadlineBridge:

    """Bridge which provides readline-like commands for the current QLineEdit.

    Attributes:
        deleted: Mapping from widgets to their last deleted text.
    """

    def __init__(self):
        self.deleted = {}

    @property
    def widget(self):
        """Get the currently active QLineEdit."""
        w = QApplication.instance().focusWidget()
        if isinstance(w, QLineEdit):
            return w
        else:
            return None

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_backward_char(self):
        """Readline: Move back a character."""
        if self.widget is None:
            return
        self.widget.cursorBackward(False)

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_forward_char(self):
        """Readline: Move forward a character."""
        if self.widget is None:
            return
        self.widget.cursorForward(False)

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_backward_word(self):
        """Readline: Move back to the start of the current or previous word."""
        if self.widget is None:
            return
        self.widget.cursorWordBackward(False)

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_forward_word(self):
        """Readline: Move forward to the end of the next word."""
        if self.widget is None:
            return
        self.widget.cursorWordForward(False)

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_beginning_of_line(self):
        """Readline: Move to the start of the current line."""
        if self.widget is None:
            return
        self.widget.home(False)

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_end_of_line(self):
        """Readline: Move to the end of the line."""
        if self.widget is None:
            return
        self.widget.end(False)

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_unix_line_discard(self):
        """Readline: Kill backward from cursor to the beginning of the line."""
        if self.widget is None:
            return
        self.widget.home(True)
        self.deleted[self.widget] = self.widget.selectedText()
        self.widget.del_()

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_kill_line(self):
        """Readline: Kill the text from point to the end of the line."""
        if self.widget is None:
            return
        self.widget.end(True)
        self.deleted[self.widget] = self.widget.selectedText()
        self.widget.del_()

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_unix_word_rubout(self):
        """Readline: Kill the word behind point."""
        if self.widget is None:
            return
        self.widget.cursorWordBackward(True)
        self.deleted[self.widget] = self.widget.selectedText()
        self.widget.del_()

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_kill_word(self):
        """Readline: Kill from point to the end of the current word."""
        if self.widget is None:
            return
        self.widget.cursorWordForward(True)
        self.deleted[self.widget] = self.widget.selectedText()
        self.widget.del_()

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_yank(self):
        """Readline: Yank the top of the kill ring into the buffer at point."""
        if self.widget is None or self.widget not in self.deleted:
            return
        self.widget.insert(self.deleted[self.widget])

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_delete_char(self):
        """Readline: Delete the character at point."""
        if self.widget is None:
            return
        self.widget.del_()

    @cmd.register(instance='rl_bridge', hide=True,
                  modes=[KeyMode.command, KeyMode.prompt])
    def rl_backward_delete_char(self):
        """Readline: Delete the character behind the cursor."""
        if self.widget is None:
            return
        self.widget.backspace()
