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

import logging

from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QLineEdit, QSizePolicy
from PyQt5.QtGui import QValidator

import qutebrowser.keyinput.modeman as modeman
import qutebrowser.commands.utils as cmdutils
from qutebrowser.commands.managers import split_cmdline
from qutebrowser.keyinput.modeparsers import STARTCHARS
from qutebrowser.models.cmdhistory import (History, HistoryEmptyError,
                                           HistoryEndReachedError)


class Command(QLineEdit):

    """The commandline part of the statusbar.

    Attributes:
        history: The command history object.
        _statusbar: The statusbar (parent) QWidget.
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
        show_cmd: Emitted when command input should be shown.
        hide_cmd: Emitted when command input can be hidden.
    """

    got_cmd = pyqtSignal(str)
    got_search = pyqtSignal(str)
    got_search_rev = pyqtSignal(str)
    clear_completion_selection = pyqtSignal()
    hide_completion = pyqtSignal()
    show_cmd = pyqtSignal()
    hide_cmd = pyqtSignal()

    # FIXME won't the tab key switch to the next widget?
    # See http://www.saltycrane.com/blog/2008/01/how-to-capture-tab-key-press-event-with/
    # for a possible fix.

    def __init__(self, statusbar):
        super().__init__(statusbar)
        self._statusbar = statusbar
        self.setStyleSheet("""
            QLineEdit {
                border: 0px;
                padding-left: 1px;
                background-color: transparent;
            }
        """)
        self.history = History()
        self._validator = _CommandValidator(self)
        self.setValidator(self._validator)
        self.textEdited.connect(self.history.stop)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Ignored)

    @pyqtSlot(str)
    def set_cmd_text(self, text):
        """Preset the statusbar to some text.

        Args:
            text: The text to set (string).

        Emit:
            textEdited: Emitted if the text changed.
        """
        old_text = self.text()
        self.setText(text)
        if old_text != text:
            # We want the completion to pop out here.
            self.textEdited.emit(text)
        self.setFocus()
        self.show_cmd.emit()

    @pyqtSlot(str)
    def on_change_completed_part(self, newtext):
        """Change the part we're currently completing in the commandline.

        Args:
            text: The text to set (string).
        """
        # FIXME we should consider the cursor position.
        text = self.text()
        if text[0] in STARTCHARS:
            prefix = text[0]
            text = text[1:]
        else:
            prefix = ''
        parts = split_cmdline(text)
        logging.debug("Old text: '{}' - parts: '{}', changing to '{}".format(
            text, parts, newtext))
        parts[-1] = newtext
        self.setText(prefix + ' '.join(parts))
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
