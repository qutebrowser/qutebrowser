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

"""Prompt shown in the statusbar."""

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QEventLoop
from PyQt5.QtWidgets import QHBoxLayout, QWidget, QLineEdit

import qutebrowser.keyinput.modeman as modeman
import qutebrowser.commands.utils as cmdutils
from qutebrowser.widgets.statusbar.textbase import TextBase
from qutebrowser.widgets.misc import MinimalLineEdit
from qutebrowser.utils.usertypes import PromptMode, Question


class Prompt(QWidget):

    """The prompt widget shown in the statusbar.

    Attributes:
        question: A Question object with the question to be asked to the user.
        loop: A local QEventLoop to spin in exec_.
        _hbox: The QHBoxLayout used to display the text and prompt.
        _txt: The TextBase instance (QLabel) used to display the prompt text.
        _input: The MinimalLineEdit instance (QLineEdit) used for the input.

    Signals:
        show_prompt: Emitted when the prompt widget wants to be shown.
        hide_prompt: Emitted when the prompt widget wants to be hidden.
        cancelled: Emitted when the prompt was cancelled by the user.
    """

    show_prompt = pyqtSignal()
    hide_prompt = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.question = None
        self.loop = QEventLoop()

        self._hbox = QHBoxLayout(self)
        self._hbox.setContentsMargins(0, 0, 0, 0)
        self._hbox.setSpacing(5)

        self._txt = TextBase()
        self._hbox.addWidget(self._txt)

        self._input = MinimalLineEdit()
        self._hbox.addWidget(self._input)

    def on_mode_left(self, mode):
        """Clear and reset input when the mode was left.

        Emit:
            cancelled: Emitted when the mode was forcibly left by the user
                       without answering the question.
        """
        if mode in ('prompt', 'yesno'):
            self._txt.setText('')
            self._input.clear()
            self._input.setEchoMode(QLineEdit.Normal)
            self.hide_prompt.emit()
            if self.question.answer is None:
                self.cancelled.emit()

    @cmdutils.register(instance='mainwindow.status.prompt', hide=True,
                       modes=['prompt'])
    def prompt_accept(self):
        """Accept the prompt.

        This executes the next action depending on the question mode, e.g. asks
        for the password or leaves the mode.
        """
        if (self.question.mode == PromptMode.user_pwd and
                self.question.user is None):
            # User just entered an username
            self.question.user = self._input.text()
            self._txt.setText("Password:")
            self._input.clear()
            self._input.setEchoMode(QLineEdit.Password)
        elif self.question.mode == PromptMode.user_pwd:
            # User just entered a password
            password = self._input.text()
            self.question.answer = (self.question.user, password)
            modeman.leave('prompt', 'prompt accept')
            self.hide_prompt.emit()
            self.question.answered.emit()
        elif self.question.mode == PromptMode.text:
            # User just entered text.
            self.question.answer = self._input.text()
            modeman.leave('prompt', 'prompt accept')
            self.question.answered.emit()
        elif self.question.mode == PromptMode.yesno:
            # User wants to accept the default of a yes/no question.
            self.question.answer = self.question.default
            modeman.leave('yesno', 'yesno accept')
            self.question.answered.emit()
        elif self.question.mode == PromptMode.alert:
            # User acknowledged an alert
            self.question.answer = None
            modeman.leave('prompt', 'alert accept')
            self.question.answered.emit()
        else:
            raise ValueError("Invalid question mode!")

    @cmdutils.register(instance='mainwindow.status.prompt', hide=True,
                       modes=['yesno'])
    def prompt_yes(self):
        """Answer yes to a yes/no prompt."""
        if self.question.mode != PromptMode.yesno:
            # We just ignore this if we don't have a yes/no question.
            return
        self.question.answer = True
        modeman.leave('yesno', 'yesno accept')
        self.question.answered.emit()
        self.question.answered_yes.emit()

    @cmdutils.register(instance='mainwindow.status.prompt', hide=True,
                       modes=['yesno'])
    def prompt_no(self):
        """Answer no to a yes/no prompt."""
        if self.question.mode != PromptMode.yesno:
            # We just ignore this if we don't have a yes/no question.
            return
        self.question.answer = False
        modeman.leave('yesno', 'prompt accept')
        self.question.answered.emit()
        self.question.answered_no.emit()

    def display(self):
        """Display the question in self.question in the widget.

        Raise:
            ValueError if the set PromptMode is invalid.
        """
        q = self.question
        if q.mode == PromptMode.yesno:
            if q.default is None:
                suffix = ""
            elif q.default:
                suffix = " (yes)"
            else:
                suffix = " (no)"
            self._txt.setText(q.text + suffix)
            self._input.hide()
            mode = 'yesno'
        elif q.mode == PromptMode.text:
            self._txt.setText(q.text)
            if q.default:
                self._input.setText(q.default)
            self._input.show()
            mode = 'prompt'
        elif q.mode == PromptMode.user_pwd:
            self._txt.setText(q.text)
            if q.default:
                self._input.setText(q.default)
            self._input.show()
            mode = 'prompt'
        elif q.mode == PromptMode.alert:
            self._txt.setText(q.text + ' (ok)')
            self._input.hide()
            mode = 'prompt'
        else:
            raise ValueError("Invalid prompt mode!")
        self._input.setFocus()
        self.show_prompt.emit()
        modeman.enter(mode, 'question asked')

    @pyqtSlot(Question, bool)
    def ask_question(self, question, blocking):
        """Slot which is called when there's a question to ask to the user.

        Return:
            The answer of the user when blocking=True.
            None if blocking=False.

        Args:
            question: The Question object to ask.
            blocking: If True, exec_ is called and the result is returned.
        """
        self.question = question
        self.display()
        if blocking:
            return self.exec_()

    def exec_(self):
        """Local eventloop to spin in for a blocking question.

        Return:
            The answer to the question. No, it's not always 42.
        """
        self.question.answered.connect(self.loop.quit)
        self.cancelled.connect(self.loop.quit)
        self.loop.exec_()
        return self.question.answer
