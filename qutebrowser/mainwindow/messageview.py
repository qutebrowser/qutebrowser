# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Showing messages above the statusbar."""

import time
from typing import MutableSequence, Optional

from qutebrowser.qt.core import pyqtSlot, pyqtSignal, QTimer, Qt
from qutebrowser.qt.widgets import QWidget, QVBoxLayout, QLabel, QSizePolicy

from qutebrowser.config import config, stylesheet
from qutebrowser.utils import usertypes, message


class Message(QLabel):

    """A single error/warning/info message."""

    def __init__(
            self,
            level: usertypes.MessageLevel,
            text: str,
            replace: Optional[str],
            text_format: Qt.TextFormat,
            parent: QWidget = None,
            created_at: Optional[float] = None,
    ) -> None:
        super().__init__(text, parent)
        self.replace = replace
        self.level = level
        if created_at is None:
            self.created_at = time.time() * 1000
        else:
            self.created_at = created_at
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWordWrap(True)
        self.setTextFormat(text_format)
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
        stylesheet.set_register(self, qss, update=False)

    @staticmethod
    def _text_format(info: message.MessageInfo) -> Qt.TextFormat:
        """The Qt.TextFormat to use based on the given MessageInfo."""
        return Qt.TextFormat.RichText if info.rich else Qt.TextFormat.PlainText

    @classmethod
    def from_info(cls, info: message.MessageInfo, parent: QWidget = None) -> "Message":
        return cls(
            level=info.level,
            text=info.text,
            replace=info.replace,
            text_format=cls._text_format(info),
            parent=parent,
        )

    def update_from_info(self, info: message.MessageInfo) -> None:
        """Update the text from the given info.

        Both the message this gets called on and the given MessageInfo need to have
        the same level.
        """
        assert self.level == info.level, (self, info)
        self.setTextFormat(self._text_format(info))
        self.setText(info.text)


class MessageView(QWidget):

    """Widget which stacks error/warning/info messages."""

    update_geometry = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._messages: MutableSequence[Message] = []
        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._clear_timer = QTimer()
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self.update)
        config.instance.changed.connect(self._set_clear_timer_interval)

        self._last_info = None

    @config.change_filter('messages.timeout')
    def _set_clear_timer_interval(self):
        """Handle message timeout setting changes."""
        self.update()

    def _remove_message(self, widget):
        """Fully remove and destroy widget from this object."""
        self._vbox.removeWidget(widget)
        widget.hide()
        widget.deleteLater()

    @pyqtSlot()
    def clear_messages(self):
        """Hide and delete all messages."""
        self.update(force_clear=True)

    @pyqtSlot()
    def update(self, force_clear=False):
        """Delete old messages and reset timer."""
        interval = config.val.messages.timeout
        if not force_clear and interval == 0:
            self._clear_timer.stop()
            return

        now = time.time() * 1000
        while self._messages:
            if not force_clear and now - self._messages[0].created_at < interval:
                break
            self._remove_message(self._messages.pop(0))

        if self._messages:
            self._clear_timer.start(int(self._messages[0].created_at + interval - now))

        else:
            self._last_info = None
            self.hide()
            self._clear_timer.stop()

        self.update_geometry.emit()

    @pyqtSlot(message.MessageInfo)
    def show_message(self, info: message.MessageInfo) -> None:
        """Show the given message with the given MessageLevel."""
        if info == self._last_info:
            return

        if info.replace is not None:
            existing = [msg for msg in self._messages if msg.replace == info.replace]
            if existing:
                assert len(existing) == 1, existing
                existing[0].update_from_info(info)
                self.update_geometry.emit()
                return

        widget = Message.from_info(info)
        self._vbox.addWidget(widget)
        widget.show()
        self._messages.append(widget)
        self._last_info = info
        self.show()
        self.update_geometry.emit()
        self.update()

    def mousePressEvent(self, e):
        """Clear messages when they are clicked on."""
        if e.button() in [Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton]:
            self.clear_messages()
