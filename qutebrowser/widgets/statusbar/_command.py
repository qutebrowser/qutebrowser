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

"""The commandline in the statusbar."""

from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtGui import QValidator

import qutebrowser.keyinput.modeman as modeman
import qutebrowser.commands.utils as cmdutils
from qutebrowser.widgets.misc import MinimalLineEdit
from qutebrowser.commands.managers import split_cmdline
from qutebrowser.keyinput.modeparsers import STARTCHARS
from qutebrowser.utils.log import completion as logger
from qutebrowser.models.cmdhistory import (History, HistoryEmptyError,
                                           HistoryEndReachedError)


class Command(MinimalLineEdit):

    """The commandline part of the statusbar.

    Attributes:
        history: The command history object.
        _validator: The current command validator.

    Signals:
        got_cmd: Emitted when a command is triggered by the user.
                 arg: The command string.
        got_search: Emitted when the user started a new search.
                    arg: The search term.
        got_rev_search: Emitted when the user started a new reverse search.
                        arg: The search term.
        clear_completion_selection: Emitted before the completion widget is
                                    hidden.
        hide_completion: Emitted when the completion widget should be hidden.
        update_completion: Emitted when the completion should be shown/updated.
                           arg 0: The new text which was set.
                           arg 1: The part the cursor is currently in.
        show_cmd: Emitted when command input should be shown.
        hide_cmd: Emitted when command input can be hidden.
    """

    got_cmd = pyqtSignal(str)
    got_search = pyqtSignal(str)
    got_search_rev = pyqtSignal(str)
    clear_completion_selection = pyqtSignal()
    hide_completion = pyqtSignal()
    update_completion = pyqtSignal(str, int)
    show_cmd = pyqtSignal()
    hide_cmd = pyqtSignal()

    # FIXME won't the tab key switch to the next widget?
    # See http://www.saltycrane.com/blog/2008/01/how-to-capture-tab-key-press-event-with/
    # for a possible fix.

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = History()
        self._validator = _CommandValidator(self)
        self.setValidator(self._validator)
        self.textEdited.connect(self.on_text_edited)
        self.cursorPositionChanged.connect(self.on_cursor_position_changed)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Ignored)

    def _cursor_part(self):
        """Get the part index of the commandline where the cursor is over."""
        prefix, parts = self._split()
        cursor_pos = self.cursorPosition()
        cursor_pos -= len(prefix)
        for i, part in enumerate(parts):
            logger.debug("part {}, len {}, pos {}".format(i, len(part),
                cursor_pos))
            if cursor_pos <= len(part):
                # foo| bar
                return i
            cursor_pos -= (len(part) + 1)  # FIXME are spaces always 1 char?

    def _split(self):
        text = self.text()
        if not text:
            return '', []
        if text[0] in STARTCHARS:
            prefix = text[0]
            text = text[1:]
        else:
            prefix = ''
        parts = split_cmdline(text)
        return prefix, parts

    @pyqtSlot(str)
    def set_cmd_text(self, text):
        """Preset the statusbar to some text.

        Args:
            text: The text to set (string).

        Emit:
            update_completion: Emitted if the text changed.
        """
        old_text = self.text()
        self.setText(text)
        if old_text != text:
            # We want the completion to pop out here.
            self.update_completion.emit(text, self._cursor_part())
        self.setFocus()
        self.show_cmd.emit()

    @pyqtSlot(str)
    def on_change_completed_part(self, newtext):
        """Change the part we're currently completing in the commandline.

        Args:
            text: The text to set (string).
        """
        prefix, parts = self._split()
        cursor_part = self._cursor_part()
        logger.debug("parts: {}, changing {} to '{}'".format(
            parts, cursor_part, newtext))
        parts[cursor_part] = newtext
        self.blockSignals(True)
        self.setText(prefix + ' '.join(parts))
        self.blockSignals(False)
        self.setFocus()
        self.show_cmd.emit()

    @cmdutils.register(instance='mainwindow.status.cmd', hide=True,
                       modes=['command'])
    def command_history_prev(self):
        """Handle Up presses (go back in history)."""
        try:
            if not self.history.browsing:
                item = self.history.start(self.text().strip())
            else:
                item = self.history.previtem()
        except (HistoryEmptyError, HistoryEndReachedError):
            return
        if item:
            self.set_cmd_text(item)

    @cmdutils.register(instance='mainwindow.status.cmd', hide=True,
                       modes=['command'])
    def command_history_next(self):
        """Handle Down presses (go forward in history)."""
        if not self.history.browsing:
            return
        try:
            item = self.history.nextitem()
        except HistoryEndReachedError:
            return
        if item:
            self.set_cmd_text(item)

    @cmdutils.register(instance='mainwindow.status.cmd', hide=True,
                       modes=['command'])
    def command_accept(self):
        """Handle the command in the status bar.

        Emit:
            got_cmd: If a new cmd was entered.
            got_search: If a new search was entered.
            got_search_rev: If a new reverse search was entered.
        """
        signals = {
            ':': self.got_cmd,
            '/': self.got_search,
            '?': self.got_search_rev,
        }
        text = self.text()
        self.history.append(text)
        modeman.leave('command', 'cmd accept')
        if text[0] in signals:
            signals[text[0]].emit(text.lstrip(text[0]))

    @pyqtSlot(str)
    def on_text_edited(self, text):
        """Slot for textEdited. Stop history and update completion."""
        self.history.stop()
        self.update_completion.emit(text, self._cursor_part())

    @pyqtSlot(int, int)
    def on_cursor_position_changed(self, _old, _new):
        """Slot for cursorPositionChanged to update completion."""
        self.update_completion.emit(self.text(), self._cursor_part())

    def on_mode_left(self, mode):
        """Clear up when ommand mode was left.

        - Clear the statusbar text if it's explicitely unfocused.
        - Clear completion selection
        - Hide completion

        Args:
            mode: The mode which was left.

        Emit:
            clear_completion_selection: Always emitted.
            hide_completion: Always emitted so the completion is hidden.
        """
        if mode == "command":
            self.setText('')
            self.history.stop()
            self.hide_cmd.emit()
            self.clear_completion_selection.emit()
            self.hide_completion.emit()

    def focusInEvent(self, e):
        """Extend focusInEvent to enter command mode."""
        modeman.enter('command', 'cmd focus')
        super().focusInEvent(e)


class _CommandValidator(QValidator):

    """Validator to prevent the : from getting deleted."""

    def validate(self, string, pos):
        """Override QValidator::validate.

        Args:
            string: The string to validate.
            pos: The current curser position.

        Return:
            A tuple (status, string, pos) as a QValidator should.
        """
        if any(string.startswith(c) for c in STARTCHARS):
            return (QValidator.Acceptable, string, pos)
        else:
            return (QValidator.Invalid, string, pos)
