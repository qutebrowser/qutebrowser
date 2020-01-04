# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Showing messages above the statusbar."""

import typing

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QTimer, Qt, QSize
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy

from qutebrowser.config import config, stylesheet
from qutebrowser.utils import usertypes


class Message(QLabel):

    """A single error/warning/info message."""

    def __init__(self, level, text, replace, parent=None):
        super().__init__(text, parent)
        self.replace = replace
        self.setAttribute(Qt.WA_StyledBackground, True)
        qss = """
            padding-top: 2px;
            padding-bottom: 2px;
        """
        if level == usertypes.MessageLevel.error:
            qss += """
                background-color: {{ conf.colors.messages.error.bg }};
                color: {{ conf.colors.messages.error.fg }};
                font: {{ conf.fonts.messages.error }};
                border-bottom: 1px solid {{ conf.colors.messages.error.border }};
            """
        elif level == usertypes.MessageLevel.warning:
            qss += """
                background-color: {{ conf.colors.messages.warning.bg }};
                color: {{ conf.colors.messages.warning.fg }};
                font: {{ conf.fonts.messages.warning }};
                border-bottom:
                    1px solid {{ conf.colors.messages.warning.border }};
            """
        elif level == usertypes.MessageLevel.info:
            qss += """
                background-color: {{ conf.colors.messages.info.bg }};
                color: {{ conf.colors.messages.info.fg }};
                font: {{ conf.fonts.messages.info }};
                border-bottom: 1px solid {{ conf.colors.messages.info.border }}
            """
        else:  # pragma: no cover
            raise ValueError("Invalid level {!r}".format(level))
        # We don't bother with set_register_stylesheet here as it's short-lived
        # anyways.
        stylesheet.set_register(self, qss, update=False)


class MessageView(QWidget):

    """Widget which stacks error/warning/info messages."""

    update_geometry = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages = []  # type: typing.MutableSequence[Message]
        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._clear_timer = QTimer()
        self._clear_timer.timeout.connect(self.clear_messages)
        config.instance.changed.connect(self._set_clear_timer_interval)

        self._last_text = None

    def sizeHint(self):
        """Get the proposed height for the view."""
        height = sum(label.sizeHint().height() for label in self._messages)
        # The width isn't really relevant as we're expanding anyways.
        return QSize(-1, height)

    @config.change_filter('messages.timeout')
    def _set_clear_timer_interval(self):
        """Configure self._clear_timer according to the config."""
        interval = config.val.messages.timeout
        if interval > 0:
            interval *= min(5, len(self._messages))
            self._clear_timer.setInterval(interval)

    def _remove_message(self, widget):
        """Fully remove and destroy widget from this object."""
        self._vbox.removeWidget(widget)
        widget.hide()
        widget.deleteLater()

    @pyqtSlot()
    def clear_messages(self):
        """Hide and delete all messages."""
        for widget in self._messages:
            self._remove_message(widget)
        self._messages = []
        self._last_text = None
        self.hide()
        self._clear_timer.stop()

    @pyqtSlot(usertypes.MessageLevel, str, bool)
    def show_message(self, level, text, replace=False):
        """Show the given message with the given MessageLevel."""
        if text == self._last_text:
            return

        if replace and self._messages and self._messages[-1].replace:
            self._remove_message(self._messages.pop())

        widget = Message(level, text, replace=replace, parent=self)
        self._vbox.addWidget(widget)
        widget.show()
        self._messages.append(widget)
        self._last_text = text
        self.show()
        self.update_geometry.emit()
        if config.val.messages.timeout != 0:
            self._set_clear_timer_interval()
            self._clear_timer.start()

    def mousePressEvent(self, e):
        """Clear messages when they are clicked on."""
        if e.button() in [Qt.LeftButton, Qt.MiddleButton, Qt.RightButton]:
            self.clear_messages()
