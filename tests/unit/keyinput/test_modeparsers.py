# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
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

"""Tests for mode parsers."""

from unittest import mock

from PyQt5.QtCore import Qt

import pytest

from qutebrowser.keyinput import modeparsers


CONFIG = {'input': {'partial-timeout': 100}}


class TestsNormalKeyParser:

    """Tests for NormalKeyParser.

    Attributes:
        kp: The NormalKeyParser to be tested.
    """

    @pytest.fixture(autouse=True)
    def patch_stuff(self, monkeypatch, stubs, config_stub, fake_keyconfig):
        """Set up mocks and read the test config."""
        monkeypatch.setattr(
            'qutebrowser.keyinput.basekeyparser.usertypes.Timer',
            stubs.FakeTimer)
        config_stub.data = CONFIG
        monkeypatch.setattr('qutebrowser.keyinput.modeparsers.config',
                            config_stub)

    @pytest.fixture
    def keyparser(self):
        kp = modeparsers.NormalKeyParser(0)
        kp.execute = mock.Mock()
        return kp

    def test_keychain(self, keyparser, fake_keyevent_factory):
        """Test valid keychain."""
        # Press 'x' which is ignored because of no match
        keyparser.handle(fake_keyevent_factory(Qt.Key_X, text='x'))
        # Then start the real chain
        keyparser.handle(fake_keyevent_factory(Qt.Key_B, text='b'))
        keyparser.handle(fake_keyevent_factory(Qt.Key_A, text='a'))
        keyparser.execute.assert_called_once_with('ba', keyparser.Type.chain,
                                                  None)
        assert keyparser._keystring == ''

    def test_partial_keychain_timeout(self, keyparser, fake_keyevent_factory):
        """Test partial keychain timeout."""
        timer = keyparser._partial_timer
        assert not timer.isActive()
        # Press 'b' for a partial match.
        # Then we check if the timer has been set up correctly
        keyparser.handle(fake_keyevent_factory(Qt.Key_B, text='b'))
        assert timer.isSingleShot()
        assert timer.interval() == 100
        assert timer.isActive()

        assert not keyparser.execute.called
        assert keyparser._keystring == 'b'
        # Now simulate a timeout and check the keystring has been cleared.
        keystring_updated_mock = mock.Mock()
        keyparser.keystring_updated.connect(keystring_updated_mock)
        timer.timeout.emit()
        assert not keyparser.execute.called
        assert keyparser._keystring == ''
        keystring_updated_mock.assert_called_once_with('')
