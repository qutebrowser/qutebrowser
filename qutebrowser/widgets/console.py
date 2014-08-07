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

"""Debugging console."""

from code import InteractiveInterpreter

from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QObject
from PyQt5.QtWidgets import QLineEdit, QTextEdit, QWidget, QVBoxLayout
from qutebrowser.models.cmdhistory import (History, HistoryEmptyError,
                                           HistoryEndReachedError)


class ConsoleInteractiveInterpreter(InteractiveInterpreter, QObject):

    """Subclass of InteractiveInterpreter to use a signal instead of stderr.

    FIXME: This approach doesn't actually work.
    """

    write_output = pyqtSignal(str)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        InteractiveInterpreter.__init__(self)

    def write(self, data):
        self.write_output.emit(data)


class ConsoleLineEdit(QLineEdit):

    """A QLineEdit which executes entered code and provides a history."""

    write = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._more = False
        self._buffer = []
        self._interpreter = ConsoleInteractiveInterpreter()
        self._interpreter.write_output.connect(self.write)
        self.history = History()
        self.returnPressed.connect(self.execute)

    @pyqtSlot(str)
    def execute(self):
        """Execute the line of code which was entered."""
        text = self.text()
        self.history.append(text)
        self.push(text)
        self.setText('')

    def push(self, line):
        """Push a line to the interpreter."""
        self._buffer.append(line)
        source = '\n'.join(self._buffer)
        self._more = self._interpreter.runsource(source, '<console>')
        if not self._more:
            self._buffer = []

    def history_prev(self):
        """Go back in the history."""
        try:
            if not self.history.browsing:
                item = self.history.start(self.text().strip())
            else:
                item = self.history.previtem()
        except (HistoryEmptyError, HistoryEndReachedError):
            return
        self.setText(item)

    def history_next(self):
        """Go forward in the history."""
        if not self.history.browsing:
            return
        try:
            item = self.history.nextitem()
        except HistoryEndReachedError:
            return
        self.setText(item)

    def keyPressEvent(self, e):
        """Override keyPressEvent to handle up/down keypresses."""
        if e.key() == Qt.Key_Up:
            self.history_prev()
            e.accept()
        elif e.key() == Qt.Key_Down:
            self.history_next()
            e.accept()
        else:
            super().keyPressEvent(e)


class ConsoleWidget(QWidget):

    """A widget with an interactive Python console."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineedit = ConsoleLineEdit()
        self.output = QTextEdit(acceptRichText=True, readOnly=True)
        self.lineedit.write.connect(self.output.append)
        self.vbox = QVBoxLayout()
        self.vbox.setSpacing(0)
        self.vbox.addWidget(self.output)
        self.vbox.addWidget(self.lineedit)
        self.setLayout(self.vbox)
