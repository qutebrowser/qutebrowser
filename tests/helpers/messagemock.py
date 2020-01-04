# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""pytest helper to monkeypatch the message module."""

import logging

import attr
import pytest

from qutebrowser.utils import usertypes, message, objreg


@attr.s
class Message:

    """Information about a shown message."""

    level = attr.ib()
    text = attr.ib()


class MessageMock:

    """Helper object for message_mock.

    Attributes:
        Message: A object representing a message.
        messages: A list of Message objects.
    """

    def __init__(self):
        self.messages = []

    def _record_message(self, level, text):
        log_levels = {
            usertypes.MessageLevel.error: logging.ERROR,
            usertypes.MessageLevel.info: logging.INFO,
            usertypes.MessageLevel.warning: logging.WARNING,
        }
        log_level = log_levels[level]

        logging.getLogger('messagemock').log(log_level, text)
        self.messages.append(Message(level, text))

    def getmsg(self, level=None):
        """Get the only message in self.messages.

        Raises ValueError if there are multiple or no messages.

        Args:
            level: The message level to check against, or None.
        """
        assert len(self.messages) == 1
        msg = self.messages[0]
        if level is not None:
            assert msg.level == level
        return msg

    def patch(self):
        """Start recording messages."""
        message.global_bridge.show_message.connect(self._record_message)
        message.global_bridge._connected = True

    def unpatch(self):
        """Stop recording messages."""
        message.global_bridge.show_message.disconnect(self._record_message)


@pytest.fixture
def message_mock():
    """Fixture to get a MessageMock."""
    mmock = MessageMock()
    mmock.patch()
    yield mmock
    mmock.unpatch()


@pytest.fixture
def message_bridge(win_registry):
    """Fixture to get a MessageBridge."""
    bridge = message.MessageBridge()
    objreg.register('message-bridge', bridge, scope='window', window=0)
    yield bridge
    objreg.delete('message-bridge', scope='window', window=0)
