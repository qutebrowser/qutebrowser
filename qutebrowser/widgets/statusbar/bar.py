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

"""The main statusbar widget."""

from PyQt5.QtCore import pyqtSignal, pyqtSlot, pyqtProperty, Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QStackedLayout, QSizePolicy

import qutebrowser.keyinput.modeman as modeman
from qutebrowser.widgets.statusbar._command import Command
from qutebrowser.widgets.statusbar._progress import Progress
from qutebrowser.widgets.statusbar._text import Text
from qutebrowser.widgets.statusbar._keystring import KeyString
from qutebrowser.widgets.statusbar._percentage import Percentage
from qutebrowser.widgets.statusbar._url import Url
from qutebrowser.config.style import set_register_stylesheet, get_stylesheet


class StatusBar(QWidget):

    """The statusbar at the bottom of the mainwindow.

    Class attributes:
        STYLESHEET: The stylesheet template.

    Attributes:
        cmd: The Command widget in the statusbar.
        txt: The Text widget in the statusbar.
        keystring: The KeyString widget in the statusbar.
        percentage: The Percentage widget in the statusbar.
        url: The Url widget in the statusbar.
        prog: The Progress widget in the statusbar.
        _hbox: The main QHBoxLayout.
        _stack: The QStackedLayout with cmd/txt widgets.

    Class attributes:
        _error: If there currently is an error, accessed through the error
                property.

                For some reason we need to have this as class attribute so
                pyqtProperty works correctly.

    Signals:
        resized: Emitted when the statusbar has resized, so the completion
                 widget can adjust its size to it.
                 arg: The new size.
        moved: Emitted when the statusbar has moved, so the completion widget
               can move the the right position.
               arg: The new position.
    """

    resized = pyqtSignal('QRect')
    moved = pyqtSignal('QPoint')
    _error = False

    STYLESHEET = """
        QWidget#StatusBar[error="false"] {{
            {color[statusbar.bg]}
        }}

        QWidget#StatusBar[error="true"] {{
            {color[statusbar.bg.error]}
        }}

        QWidget {{
            {color[statusbar.fg]}
            {font[statusbar]}
        }}
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)
        self.setAttribute(Qt.WA_StyledBackground)
        set_register_stylesheet(self)

        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        self._option = None

        self._hbox = QHBoxLayout(self)
        self._hbox.setContentsMargins(0, 0, 0, 0)
        self._hbox.setSpacing(5)

        self._stack = QStackedLayout()
        self._stack.setContentsMargins(0, 0, 0, 0)

        self.cmd = Command(self)
        self._stack.addWidget(self.cmd)

        self.txt = Text(self)
        self._stack.addWidget(self.txt)

        self.cmd.show_cmd.connect(self._show_cmd_widget)
        self.cmd.hide_cmd.connect(self._hide_cmd_widget)
        self._hide_cmd_widget()

        self._hbox.addLayout(self._stack)

        self.keystring = KeyString(self)
        self._hbox.addWidget(self.keystring)

        self.url = Url(self)
        self._hbox.addWidget(self.url)

        self.percentage = Percentage(self)
        self._hbox.addWidget(self.percentage)

        self.prog = Progress(self)
        self._hbox.addWidget(self.prog)

    @pyqtProperty(bool)
    def error(self):
        """Getter for self.error, so it can be used as Qt property."""
        # pylint: disable=method-hidden
        return self._error

    @error.setter
    def error(self, val):
        """Setter for self.error, so it can be used as Qt property.

        Re-set the stylesheet after setting the value, so everything gets
        updated by Qt properly.
        """
        self._error = val
        self.setStyleSheet(get_stylesheet(self.STYLESHEET))

    def _show_cmd_widget(self):
        """Show command widget instead of temporary text."""
        self._stack.setCurrentWidget(self.cmd)
        self.clear_error()

    def _hide_cmd_widget(self):
        """Show temporary text instead of command widget."""
        self._stack.setCurrentWidget(self.txt)

    @pyqtSlot(str)
    def disp_error(self, text):
        """Display an error in the statusbar."""
        self.error = True
        self.txt.errortext = text

    @pyqtSlot()
    def clear_error(self):
        """Clear a displayed error from the status bar."""
        self.error = False
        self.txt.errortext = ''

    @pyqtSlot('QKeyEvent')
    def on_key_pressed(self, e):
        """Hide temporary error message if a key was pressed.

        Args:
            e: The original QKeyEvent.
        """
        if e.key() in [Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta]:
            # Only modifier pressed, don't hide yet.
            return
        self.txt.set_temptext('')
        self.clear_error()

    @pyqtSlot(str)
    def on_mode_entered(self, mode):
        """Mark certain modes in the commandline."""
        if mode in modeman.instance().passthrough:
            self.txt.normaltext = "-- {} MODE --".format(mode.upper())

    @pyqtSlot(str)
    def on_mode_left(self, mode):
        """Clear marked mode."""
        if mode in modeman.instance().passthrough:
            self.txt.normaltext = ""

    def resizeEvent(self, e):
        """Extend resizeEvent of QWidget to emit a resized signal afterwards.

        Args:
            e: The QResizeEvent.

        Emit:
            resized: Always emitted.
        """
        super().resizeEvent(e)
        self.resized.emit(self.geometry())

    def moveEvent(self, e):
        """Extend moveEvent of QWidget to emit a moved signal afterwards.

        Args:
            e: The QMoveEvent.

        Emit:
            moved: Always emitted.
        """
        super().moveEvent(e)
        self.moved.emit(e.pos())
