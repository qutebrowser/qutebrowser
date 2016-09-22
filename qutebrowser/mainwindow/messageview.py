# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


from PyQt5.QtCore import pyqtSlot, pyqtSignal, QTimer, Qt, QSize
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy

from qutebrowser.config import config, style
from qutebrowser.utils import usertypes, objreg


class Message(QLabel):

    """A single error/warning/info message."""

    def __init__(self, level, text, parent=None):
        super().__init__(text, parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        stylesheet = """
            padding-top: 2px;
            padding-bottom: 2px;
        """
        if level == usertypes.MessageLevel.error:
            stylesheet += """
                background-color: {{ color['messages.bg.error'] }};
                color: {{ color['messages.fg.error'] }};
                font: {{ font['messages.error'] }};
                border-bottom: 1px solid {{ color['messages.border.error'] }};
            """
        elif level == usertypes.MessageLevel.warning:
            stylesheet += """
                background-color: {{ color['messages.bg.warning'] }};
                color: {{ color['messages.fg.warning'] }};
                font: {{ font['messages.warning'] }};
                border-bottom:
                    1px solid {{ color['messages.border.warning'] }};
            """
        elif level == usertypes.MessageLevel.info:
            stylesheet += """
                background-color: {{ color['messages.bg.info'] }};
                color: {{ color['messages.fg.info'] }};
                font: {{ font['messages.info'] }};
                border-bottom: 1px solid {{ color['messages.border.info'] }}
            """
        else:  # pragma: no cover
            raise ValueError("Invalid level {!r}".format(level))
        # We don't bother with set_register_stylesheet here as it's short-lived
        # anyways.
        self.setStyleSheet(style.get_stylesheet(stylesheet))


class MessageView(QWidget):

    """Widget which stacks error/warning/info messages."""

    update_geometry = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._clear_timer = QTimer()
        self._clear_timer.timeout.connect(self._clear_messages)
        self._set_clear_timer_interval()
        objreg.get('config').changed.connect(self._set_clear_timer_interval)

        self._last_text = None
        self._messages = []

    def sizeHint(self):
        """Get the proposed height for the view."""
        height = sum(label.sizeHint().height() for label in self._messages)
        # The width isn't really relevant as we're expanding anyways.
        return QSize(-1, height)

    @config.change_filter('ui', 'message-timeout')
    def _set_clear_timer_interval(self):
        """Configure self._clear_timer according to the config."""
        self._clear_timer.setInterval(config.get('ui', 'message-timeout'))

    @pyqtSlot()
    def _clear_messages(self):
        """Hide and delete all messages."""
        for widget in self._messages:
            self._vbox.removeWidget(widget)
            widget.hide()
            widget.deleteLater()
        self._messages = []
        self._last_text = None
        self.hide()
        self._clear_timer.stop()

    @pyqtSlot(usertypes.MessageLevel, str)
    def show_message(self, level, text):
        """Show the given message with the given MessageLevel."""
        if text == self._last_text:
            return

        widget = Message(level, text, parent=self)
        self._vbox.addWidget(widget)
        widget.show()
        self._clear_timer.start()
        self._messages.append(widget)
        self._last_text = text
        self.show()
        self.update_geometry.emit()
