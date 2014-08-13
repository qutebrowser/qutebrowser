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

"""Misc. widgets used at different places."""

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtGui import QValidator

from qutebrowser.models.cmdhistory import History


class MinimalLineEditMixin:

    """A mixin to give a QLineEdit a minimal look and nicer repr()."""

    def __init__(self):
        self.setStyleSheet("""
            QLineEdit {
                border: 0px;
                padding-left: 1px;
                background-color: transparent;
            }
        """)

    def __repr__(self):
        return '<{} "{}">'.format(self.__class__.__name__, self.text())


class CommandLineEdit(QLineEdit):

    """A QLineEdit with a history and prompt chars.

    Attributes:
        history: The command history object.
        _validator: The current command validator.
    """

    def __init__(self, parent, validator):
        """Constructor.

        Args:
            validator: A function which checks if a given input is valid.
        """
        super().__init__(parent)
        self.history = History()
        self._validator = _CommandValidator(validator, parent=self)
        self.setValidator(self._validator)
        self.textEdited.connect(self.on_text_edited)

    @pyqtSlot(str)
    def on_text_edited(self, _text):
        """Slot for textEdited. Stop history browsing."""
        self.history.stop()

    def __repr__(self):
        return '<{} "{}">'.format(self.__class__.__name__, self.text())


class _CommandValidator(QValidator):

    """Validator to prevent the : from getting deleted."""

    def __init__(self, validator, parent=None):
        super().__init__(parent)
        self.validator = validator

    def validate(self, string, pos):
        """Override QValidator::validate.

        Args:
            string: The string to validate.
            pos: The current curser position.

        Return:
            A tuple (status, string, pos) as a QValidator should.
        """
        if self.validator(string):
            return (QValidator.Acceptable, string, pos)
        else:
            return (QValidator.Invalid, string, pos)
