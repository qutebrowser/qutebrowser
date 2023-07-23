# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""pytest helper to monkeypatch the message module."""

import logging

import pytest
from qutebrowser.qt.core import pyqtSlot, pyqtSignal, QObject

from qutebrowser.utils import usertypes, message


class MessageMock(QObject):

    """Helper object for message_mock.

    Attributes:
        messages: A list of Message objects.
        questions: A list of Question objects.
        _logger: The logger to use for messages/questions.
    """

    got_message = pyqtSignal(message.MessageInfo)
    got_question = pyqtSignal(usertypes.Question)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages = []
        self.questions = []
        self._logger = logging.getLogger('messagemock')

    @pyqtSlot(message.MessageInfo)
    def _record_message(self, info):
        self.got_message.emit(info)
        log_levels = {
            usertypes.MessageLevel.error: logging.ERROR,
            usertypes.MessageLevel.info: logging.INFO,
            usertypes.MessageLevel.warning: logging.WARNING,
        }
        log_level = log_levels[info.level]

        self._logger.log(log_level, info.text)
        self.messages.append(info)

    @pyqtSlot(usertypes.Question)
    def _record_question(self, question):
        self.got_question.emit(question)
        self._logger.debug(question)
        self.questions.append(question)

    def getmsg(self, level=None):
        """Get the only message in self.messages.

        Raises AssertionError if there are multiple or no messages.

        Args:
            level: The message level to check against, or None.
        """
        assert len(self.messages) == 1
        msg = self.messages[0]
        if level is not None:
            assert msg.level == level
        return msg

    def get_question(self):
        """Get the only question in self.questions.

        Raises AssertionError if there are multiple or no questions.
        """
        assert len(self.questions) == 1
        return self.questions[0]

    def connect(self):
        """Start recording messages / questions."""
        message.global_bridge.show_message.connect(self._record_message)
        message.global_bridge.ask_question.connect(self._record_question)
        message.global_bridge._connected = True

    def disconnect(self):
        """Stop recording messages/questions."""
        message.global_bridge.show_message.disconnect(self._record_message)
        message.global_bridge.ask_question.disconnect(self._record_question)


@pytest.fixture
def message_mock():
    """Fixture to get a MessageMock."""
    mmock = MessageMock()
    mmock.connect()
    yield mmock
    mmock.disconnect()
