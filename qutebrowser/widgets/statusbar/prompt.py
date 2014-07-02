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

"""Prompt shown in the statusbar."""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QWidget

from qutebrowser.widgets.misc import MinimalLineEdit
from qutebrowser.widgets.statusbar.textbase import TextBase
from qutebrowser.widgets.statusbar.prompter import Prompter


class Prompt(QWidget):

    """The prompt widget shown in the statusbar.

    Attributes:
        prompter: The Prompter instance assosciated with this Prompt.
        txt: The TextBase instance (QLabel) used to display the prompt text.
        lineedit: The MinimalLineEdit instance (QLineEdit) used for the input.
        _hbox: The QHBoxLayout used to display the text and prompt.

    Signals:
        show_prompt: Emitted when the prompt widget wants to be shown.
        hide_prompt: Emitted when the prompt widget wants to be hidden.
    """

    show_prompt = pyqtSignal()
    hide_prompt = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hbox = QHBoxLayout(self)
        self._hbox.setContentsMargins(0, 0, 0, 0)
        self._hbox.setSpacing(5)

        self.txt = TextBase()
        self._hbox.addWidget(self.txt)

        self.lineedit = MinimalLineEdit()
        self._hbox.addWidget(self.lineedit)

        self.prompter = Prompter(self)

    def __repr__(self):
        return '<{}>'.format(self.__class__.__name__)
