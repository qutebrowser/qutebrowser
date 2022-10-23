# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

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

    def test_keychain(self, keyparser, commandrunner):
        """Test valid keychain."""
        # Press 'z' which is ignored because of no match
        # Then start the real chain
        chain = keyutils.KeySequence.parse('zba')
        for info in chain:
            keyparser.handle(info.to_event())
        assert commandrunner.commands == [('message-info ba', None)]
        assert not keyparser._sequence

    def test_partial_keychain_timeout(self, keyparser, config_stub,
                                      qtbot, commandrunner):
        """Test partial keychain timeout."""
        config_stub.val.input.partial_timeout = 100
        timer = keyparser._partial_timer
        assert not timer.isActive()

        # Press 'b' for a partial match.
        # Then we check if the timer has been set up correctly
        keyparser.handle(keyutils.KeyInfo(Qt.Key_B, Qt.NoModifier).to_event())
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
    def hintmanager(self, stubs):
        return stubs.FakeHintManager()

    @pytest.fixture
    def keyparser(self, config_stub, key_config_stub, commandrunner,
                  hintmanager):
        return modeparsers.HintKeyParser(win_id=0,
                                         hintmanager=hintmanager,
                                         commandrunner=commandrunner)

    @pytest.mark.parametrize('bindings, keychain, prefix, hint', [
        (
            ['aa', 'as'],
            'as',
            'a',
            'as'
        ),
        (
            ['21', '22'],
            '<Num+2><Num+2>',
            '2',
            '22'
        ),
        (
            ['äa', 'äs'],
            'äs',
            'ä',
            'äs'
        ),
        (
            ['не', 'на'],
            'не',
            '<Н>',
            'не',
        ),
    ])
    def test_match(self, keyparser, hintmanager,
                   bindings, keychain, prefix, hint):
        keyparser.update_bindings(bindings)

        seq = keyutils.KeySequence.parse(keychain)
        assert len(seq) == 2

        match = keyparser.handle(seq[0].to_event())
        assert match == QKeySequence.PartialMatch
        assert hintmanager.keystr == prefix

        match = keyparser.handle(seq[1].to_event())
        assert match == QKeySequence.ExactMatch
        assert hintmanager.keystr == hint

    def test_match_key_mappings(self, config_stub, keyparser, hintmanager):
        config_stub.val.bindings.key_mappings = {'α': 'a', 'σ': 's'}
        keyparser.update_bindings(['aa', 'as'])

        seq = keyutils.KeySequence.parse('ασ')
        assert len(seq) == 2

        match = keyparser.handle(seq[0].to_event())
        assert match == QKeySequence.PartialMatch
        assert hintmanager.keystr == 'a'

        match = keyparser.handle(seq[1].to_event())
        assert match == QKeySequence.ExactMatch
        assert hintmanager.keystr == 'as'

    def test_command(self, keyparser, config_stub, hintmanager, commandrunner):
        config_stub.val.bindings.commands = {
            'hint': {'abc': 'message-info abc'}
        }

        keyparser.update_bindings(['xabcy'])

        steps = [
            (Qt.Key_X, QKeySequence.PartialMatch, 'x'),
            (Qt.Key_A, QKeySequence.PartialMatch, 'x'),
            (Qt.Key_B, QKeySequence.PartialMatch, 'x'),
            (Qt.Key_C, QKeySequence.ExactMatch, 'x'),
        ]
        for key, expected_match, keystr in steps:
            info = keyutils.KeyInfo(key, Qt.NoModifier)
            match = keyparser.handle(info.to_event())
            assert match == expected_match
            assert hintmanager.keystr == keystr
            if key != Qt.Key_C:
                assert not commandrunner.commands

        assert commandrunner.commands == [('message-info abc', None)]
