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

from PyQt5.QtCore import pyqtSignal, QEventLoop
from PyQt5.QtWidgets import QLineEdit, QHBoxLayout

import qutebrowser.keyinput.modeman as modeman
import qutebrowser.commands.utils as cmdutils
from qutebrowser.widgets.statusbar._textbase import TextBase
from qutebrowser.utils.usertypes import enum

PromptMode = enum('yesno', 'text', 'user_pwd')


class Prompt(TextBase):

    answered = pyqtSignal([str], [bool], [str, str])
    accepted = pyqtSignal()
    hide_prompt = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.mode = None
        self.default = None
        self.text = None
        self.answer = None

        self.loop = QEventLoop()

        self._hbox = QHBoxLayout(self)
        self._hbox.setContentsMargins(0, 0, 0, 0)
        self._hbox.setSpacing(5)

        self._txt = TextBase()
        self._hbox.addWidget(self._txt)

        self._input = _QueryInput()
        self._hbox.addWidget(self._input)

    def _user_entered(self):
        self._user = self._input.text()
        self._txt.setText("Password:")
        self._input.clear()
        self._input.setEchoMode(QLineEdit.Password)
        self.accepted.disconnect(self._user_entered)
        self.accepted.connect(self._password_entered)

    def _password_entered(self):
        self.accepted.disconnect(self._password_entered)
        password = self._input.text()
        self.answer = (self._user, password)
        self._txt.setText('')
        self._input.clear()
        self._input.setEchoMode(QLineEdit.Normal)
        self.default = None
        self.mode = None
        self.text = None
        self.answered[str, str].emit(*self.answer)
        modeman.leave('prompt', 'prompt accept')
        self.hide_prompt.emit()

    def on_return_pressed(self):
        self.accepted.disconnect(self.on_return_pressed)
        self.answer = self._input.text()
        self._txt.setText('')
        self.default = None
        self.mode = None
        self.text = None
        # FIXME handle bool correctly
        self.answered[str].emit(self.answer)
        modeman.leave('prompt', 'prompt accept')
        self.hide_prompt.emit()

    @cmdutils.register(instance='mainwindow.status.prompt', hide=True,
                       modes=['prompt'])
    def prompt_accept(self):
        """Accept the prompt. """
        self.accepted.emit()

    def display(self):
        if self.mode == PromptMode.yesno:
            if self.default is None:
                suffix = " [y/n]"
            elif self.default:
                suffix = " [Y/n]"
            else:
                suffix = " [y/N]"
            self._txt.setText(self.text + suffix)
            self._input.hide()
        elif self.mode == PromptMode.text:
            self._txt.setText(self.text)
            if self.default:
                self._input.setText(self.default)
            self._input.show()
            self.accepted.connect(self.on_return_pressed)
        elif self.mode == PromptMode.user_pwd:
            self._txt.setText(self.text)
            if self.default:
                self._input.setText(self.default)
            self._input.show()
            self.accepted.connect(self._user_entered)
        else:
            raise ValueError("Invalid prompt mode!")
        self._input.setFocus()

    def exec_(self):
        self.display()
        self.answered[str, str].connect(self.loop.quit)
        self.loop.exec_()
        return self.answer


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
