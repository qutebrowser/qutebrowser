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

"""pytest helper to monkeypatch the message module."""

import pytest

import collections

from qutebrowser.utils import usertypes


class MessageMock:

    """Helper object for message_mock.

    Attributes:
        _monkeypatch: The pytest monkeypatch fixture.
        MessageLevel: An enum with possible message levels.
        Message: A namedtuple representing a message.
        messages: A list of Message tuples.
    """

    Message = collections.namedtuple('Message', ['level', 'win_id', 'text',
                                                 'immediate'])
    MessageLevel = usertypes.enum('Level', ('error', 'info', 'warning'))

    def __init__(self, monkeypatch):
        self._monkeypatch = monkeypatch
        self.messages = []

    def _handle(self, level, win_id, text, immediately=False):
        self.messages.append(self.Message(level, win_id, text, immediately))

    def _handle_error(self, *args, **kwargs):
        self._handle(self.MessageLevel.error, *args, **kwargs)

    def _handle_info(self, *args, **kwargs):
        self._handle(self.MessageLevel.info, *args, **kwargs)

    def _handle_warning(self, *args, **kwargs):
        self._handle(self.MessageLevel.warning, *args, **kwargs)

    def getmsg(self):
        """Get the only message in self.messages.

        Raises ValueError if there are multiple or no messages.
        """
        if len(self.messages) != 1:
            raise ValueError("Got {} messages but expected a single "
                             "one.".format(len(self.messages)))
        return self.messages[0]

    def patch(self, module_path):
        """Patch message.* in the given module (as a string)."""
        self._monkeypatch.setattr(module_path + '.error', self._handle_error)
        self._monkeypatch.setattr(module_path + '.info', self._handle_info)
        self._monkeypatch.setattr(module_path + '.warning',
                                  self._handle_warning)


@pytest.fixture
def message_mock(monkeypatch):
    """Fixture to get a MessageMock."""
    return MessageMock(monkeypatch)
