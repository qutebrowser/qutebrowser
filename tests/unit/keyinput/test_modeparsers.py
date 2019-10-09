# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
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

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

import pytest

from qutebrowser.keyinput import modeparsers, keyutils


@pytest.fixture
def commandrunner(stubs):
    return stubs.FakeCommandRunner()


class TestsNormalKeyParser:

    @pytest.fixture(autouse=True)
    def patch_stuff(self, monkeypatch, stubs, keyinput_bindings):
        """Set up mocks and read the test config."""
        monkeypatch.setattr(
            'qutebrowser.keyinput.basekeyparser.usertypes.Timer',
            stubs.FakeTimer)

    @pytest.fixture
    def keyparser(self, commandrunner):
        kp = modeparsers.NormalKeyParser(win_id=0, commandrunner=commandrunner)
        return kp

    def test_keychain(self, keyparser, fake_keyevent, commandrunner):
        """Test valid keychain."""
        # Press 'z' which is ignored because of no match
        keyparser.handle(fake_keyevent(Qt.Key_Z))
        # Then start the real chain
        keyparser.handle(fake_keyevent(Qt.Key_B))
        keyparser.handle(fake_keyevent(Qt.Key_A))
        assert commandrunner.commands == [('message-info ba', None)]
        assert not keyparser._sequence

    def test_partial_keychain_timeout(self, keyparser, config_stub,
                                      fake_keyevent, qtbot, commandrunner):
        """Test partial keychain timeout."""
        config_stub.val.input.partial_timeout = 100
        timer = keyparser._partial_timer
        assert not timer.isActive()

        # Press 'b' for a partial match.
        # Then we check if the timer has been set up correctly
        keyparser.handle(fake_keyevent(Qt.Key_B))
        assert timer.isSingleShot()
        assert timer.interval() == 100
        assert timer.isActive()

        assert not commandrunner.commands
        assert keyparser._sequence == keyutils.KeySequence.parse('b')

        # Now simulate a timeout and check the keystring has been cleared.
        with qtbot.wait_signal(keyparser.keystring_updated) as blocker:
            timer.timeout.emit()

        assert not commandrunner.commands
        assert not keyparser._sequence
        assert blocker.args == ['']


class TestHintKeyParser:

    @pytest.fixture
    def keyparser(self, config_stub, key_config_stub, commandrunner):
        kp = modeparsers.HintKeyParser(win_id=0, commandrunner=commandrunner)
        kp.keystring_updated.disconnect()  # Don't try to update HintManager
        return kp

    def test_simple_hint_match(self, keyparser, fake_keyevent, commandrunner):
        keyparser.update_bindings(['aa', 'as'])

        match = keyparser.handle(fake_keyevent(Qt.Key_A))
        assert match == QKeySequence.PartialMatch
        match = keyparser.handle(fake_keyevent(Qt.Key_S))
        assert match == QKeySequence.ExactMatch

        assert commandrunner.commands == [('follow-hint -s as', None)]

    def test_numberkey_hint_match(self, keyparser, fake_keyevent):
        keyparser.update_bindings(['21', '22'])

        match = keyparser.handle(fake_keyevent(Qt.Key_2, Qt.KeypadModifier))
        assert match == QKeySequence.PartialMatch
        match = keyparser.handle(fake_keyevent(Qt.Key_2, Qt.KeypadModifier))
        assert match == QKeySequence.ExactMatch
