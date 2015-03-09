# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import functools

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QHBoxLayout, QWidget, QLineEdit, QSizePolicy

from qutebrowser.mainwindow.statusbar import textbase, prompter
from qutebrowser.utils import objreg, utils
from qutebrowser.misc import miscwidgets as misc


class PromptLineEdit(misc.MinimalLineEditMixin, QLineEdit):

    """QLineEdit with a minimal stylesheet."""

    def __init__(self, parent=None):
        QLineEdit.__init__(self, parent)
        misc.MinimalLineEditMixin.__init__(self)
        self.textChanged.connect(self.updateGeometry)

    def sizeHint(self):
        """Dynamically calculate the needed size."""
        height = super().sizeHint().height()
        text = self.text()
        if not text:
            text = 'x'
        width = self.fontMetrics().width(text)
        return QSize(width, height)


class Prompt(QWidget):

    """The prompt widget shown in the statusbar.

    Attributes:
        txt: The TextBase instance (QLabel) used to display the prompt text.
        lineedit: The MinimalLineEdit instance (QLineEdit) used for the input.
        _hbox: The QHBoxLayout used to display the text and prompt.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        objreg.register('prompt', self, scope='window', window=win_id)
        self._hbox = QHBoxLayout(self)
        self._hbox.setContentsMargins(0, 0, 0, 0)
        self._hbox.setSpacing(5)

        self.txt = textbase.TextBase()
        self._hbox.addWidget(self.txt)

        self.lineedit = PromptLineEdit()
        self.lineedit.setSizePolicy(QSizePolicy.MinimumExpanding,
                                    QSizePolicy.Fixed)
        self._hbox.addWidget(self.lineedit)

        prompter_obj = prompter.Prompter(win_id)
        objreg.register('prompter', prompter_obj, scope='window',
                        window=win_id)
        self.destroyed.connect(
            functools.partial(objreg.delete, 'prompter', scope='window',
                              window=win_id))

    def __repr__(self):
        return utils.get_repr(self)
