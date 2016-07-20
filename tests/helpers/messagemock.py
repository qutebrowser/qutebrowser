# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import collections

import pytest

from qutebrowser.utils import usertypes


Message = collections.namedtuple('Message', ['level', 'win_id', 'text',
                                             'immediate'])


Level = usertypes.enum('Level', ('error', 'info', 'warning'))


class MessageMock:

    """Helper object for message_mock.

    Attributes:
        _monkeypatch: The pytest monkeypatch fixture.
        Message: A namedtuple representing a message.
        messages: A list of Message tuples.
        caplog: The pytest-capturelog fixture.
        Level: The Level type for easier usage as a fixture.
    """

    Level = Level

    def __init__(self, monkeypatch, caplog):
        self._monkeypatch = monkeypatch
        self._caplog = caplog
        self.messages = []

    def _handle(self, level, win_id, text, immediately=False, *,
                stack=None):  # pylint: disable=unused-variable
        log_levels = {
            Level.error: logging.ERROR,
            Level.info: logging.INFO,
            Level.warning: logging.WARNING
        }
        log_level = log_levels[level]

        logging.getLogger('messagemock').log(log_level, text)
        self.messages.append(Message(level, win_id, text, immediately))

    def _handle_error(self, *args, **kwargs):
        self._handle(Level.error, *args, **kwargs)

    def _handle_info(self, *args, **kwargs):
        self._handle(Level.info, *args, **kwargs)

    def _handle_warning(self, *args, **kwargs):
        self._handle(Level.warning, *args, **kwargs)

    def getmsg(self, level=None, *, win_id=0, immediate=False):
        """Get the only message in self.messages.

        Raises ValueError if there are multiple or no messages.

        Args:
            level: The message level to check against, or None.
            win_id: The window id to check against.
            immediate: If the message has the immediate flag set.
        """
        assert len(self.messages) == 1
        msg = self.messages[0]

        if level is not None:
            assert msg.level == level
        assert msg.win_id == win_id
        assert msg.immediate == immediate

        return msg

    def patch(self, module_path):
        """Patch message.* in the given module (as a string)."""
        self._monkeypatch.setattr(module_path + '.error', self._handle_error)
        self._monkeypatch.setattr(module_path + '.info', self._handle_info)
        self._monkeypatch.setattr(module_path + '.warning',
                                  self._handle_warning)


@pytest.fixture
def message_mock(monkeypatch, caplog):
    """Fixture to get a MessageMock."""
    return MessageMock(monkeypatch, caplog)
