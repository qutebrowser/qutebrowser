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

from PyQt5.QtCore import pyqtSignal, QEventLoop, QObject
from PyQt5.QtWidgets import QLineEdit, QHBoxLayout

import qutebrowser.keyinput.modeman as modeman
import qutebrowser.commands.utils as cmdutils
from qutebrowser.widgets.statusbar._textbase import TextBase
from qutebrowser.utils.usertypes import enum

PromptMode = enum('yesno', 'text', 'user_pwd')


class Question(QObject):

    answered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = None
        self.default = None
        self.text = None
        self.user = None
        self._answer = None

    @property
    def answer(self):
        return self._answer

    @answer.setter
    def answer(self, val):
        self._answer = val
        self.answered.emit()


class Prompt(TextBase):

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

        self._input = _QueryInput()
        self._hbox.addWidget(self._input)

    def on_mode_left(self, mode):
        if mode == 'prompt':
            self._txt.setText('')
            self._input.clear()
            self._input.setEchoMode(QLineEdit.Normal)
            self.hide_prompt.emit()
            if self.question.answer is None:
                self.cancelled.emit()

    @cmdutils.register(instance='mainwindow.status.prompt', hide=True,
                       modes=['prompt'])
    def prompt_accept(self):
        """Accept the prompt. """
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
        else:
            # User just entered all information needed in some other mode.
            self.question.answer = self._input.text()
            modeman.leave('prompt', 'prompt accept')

    def display(self):
        q = self.question
        if q.mode == PromptMode.yesno:
            if q.default is None:
                suffix = " [y/n]"
            elif q.default:
                suffix = " [Y/n]"
            else:
                suffix = " [y/N]"
            self._txt.setText(q.text + suffix)
            self._input.hide()
        elif q.mode == PromptMode.text:
            self._txt.setText(q.text)
            if q.default:
                self._input.setText(q.default)
            self._input.show()
        elif q.mode == PromptMode.user_pwd:
            self._txt.setText(q.text)
            if q.default:
                self._input.setText(q.default)
            self._input.show()
        else:
            raise ValueError("Invalid prompt mode!")
        self._input.setFocus()
        self.show_prompt.emit()

    def exec_(self):
        self.display()
        self.question.answered.connect(self.loop.quit)
        self.cancelled.connect(self.loop.quit)
        self.loop.exec_()
        return self.question.answer


class _QueryInput(QLineEdit):

    """Minimal QLineEdit used for input."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLineEdit {
                border: 0px;
                padding-left: 1px;
                background-color: transparent;
            }
        """)

    def focusInEvent(self, e):
        """Extend focusInEvent to enter command mode."""
        modeman.enter('prompt', 'auth focus')
        super().focusInEvent(e)
