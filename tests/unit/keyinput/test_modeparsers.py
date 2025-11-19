# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for mode parsers."""

from unittest import mock

from qutebrowser.qt.core import Qt, QTimer
from qutebrowser.qt.gui import QKeySequence

import pytest

from qutebrowser.keyinput import modeparsers, keyutils
from qutebrowser.config import configexc


@pytest.fixture
def commandrunner(stubs):
    return stubs.FakeCommandRunner()


@pytest.fixture
def handle_text():
    """Helper function to handle multiple fake keypresses."""
    def func(kp, *args):
        for key in args:
            info = keyutils.KeyInfo(key, Qt.KeyboardModifier.NoModifier)
            kp.handle(info.to_event())
    return func


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
                   bindings, keychain, prefix, hint, pyqt_enum_workaround):
        with pyqt_enum_workaround(keyutils.KeyParseError):
            keyparser.update_bindings(bindings)

        seq = keyutils.KeySequence.parse(keychain)
        assert len(seq) == 2

        # pylint: disable-next=no-member
        match = keyparser.handle(seq[0].to_event())
        assert match == QKeySequence.SequenceMatch.PartialMatch
        assert hintmanager.keystr == prefix

        # pylint: disable-next=no-member
        match = keyparser.handle(seq[1].to_event())
        assert match == QKeySequence.SequenceMatch.ExactMatch
        assert hintmanager.keystr == hint

    def test_match_key_mappings(self, config_stub, keyparser, hintmanager,
                                pyqt_enum_workaround):
        with pyqt_enum_workaround(configexc.ValidationError):
            config_stub.val.bindings.key_mappings = {'α': 'a', 'σ': 's'}
        keyparser.update_bindings(['aa', 'as'])

        seq = keyutils.KeySequence.parse('ασ')
        assert len(seq) == 2

        # pylint: disable-next=no-member
        match = keyparser.handle(seq[0].to_event())
        assert match == QKeySequence.SequenceMatch.PartialMatch
        assert hintmanager.keystr == 'a'

        # pylint: disable-next=no-member
        match = keyparser.handle(seq[1].to_event())
        assert match == QKeySequence.SequenceMatch.ExactMatch
        assert hintmanager.keystr == 'as'

    def test_command(self, keyparser, config_stub, hintmanager, commandrunner):
        config_stub.val.bindings.commands = {
            'hint': {'abc': 'message-info abc'}
        }

        keyparser.update_bindings(['xabcy'])

        steps = [
            (Qt.Key.Key_X, QKeySequence.SequenceMatch.PartialMatch, 'x'),
            (Qt.Key.Key_A, QKeySequence.SequenceMatch.PartialMatch, 'x'),
            (Qt.Key.Key_B, QKeySequence.SequenceMatch.PartialMatch, 'x'),
            (Qt.Key.Key_C, QKeySequence.SequenceMatch.ExactMatch, ''),
        ]
        for key, expected_match, keystr in steps:
            info = keyutils.KeyInfo(key, Qt.KeyboardModifier.NoModifier)
            match = keyparser.handle(info.to_event())
            assert match == expected_match
            assert hintmanager.keystr == keystr
            if key != Qt.Key.Key_C:
                assert not commandrunner.commands

        assert commandrunner.commands == [('message-info abc', None)]

    @pytest.mark.parametrize('seq, hint_seq', [
        ((Qt.Key.Key_F,), None),
        ((Qt.Key.Key_F,), 'f'),
        ((Qt.Key.Key_F,), 'fz'),
        ((Qt.Key.Key_F,), 'fzz'),
        ((Qt.Key.Key_F,), 'fza'),
        ((Qt.Key.Key_F, Qt.Key.Key_G), None),
        ((Qt.Key.Key_F, Qt.Key.Key_G), 'f'),
        ((Qt.Key.Key_F, Qt.Key.Key_G), 'fg'),
        ((Qt.Key.Key_F, Qt.Key.Key_G), 'fgz'),
        ((Qt.Key.Key_F, Qt.Key.Key_G), 'fgzz'),
        ((Qt.Key.Key_F, Qt.Key.Key_G), 'fgza'),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), None),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'f'),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'fg'),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'fgh'),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'fghz'),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'fghzz'),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'fghza'),
    ])
    def test_forward_keys(self, config_stub, handle_text, keyparser, qtbot,
                          hintmanager, commandrunner, seq, hint_seq):
        command_parser = keyparser._command_parser
        config_stub.val.bindings.commands = {
            'hint': {
                'fy': 'message-info fy',
                'fgy': 'message-info fgy',
                'fghy': 'message-info fghy',
            }
        }
        if hint_seq is not None:
            keyparser.update_bindings([hint_seq, 'zz'])
        forward_partial_key = mock.Mock()
        command_parser.forward_partial_key.connect(forward_partial_key)
        handle_text(keyparser, *seq)
        assert not commandrunner.commands
        seq = list(seq) + [Qt.Key.Key_Z]
        signals = [command_parser.forward_partial_key] * len(seq)
        with qtbot.wait_signals(signals) as blocker:
            handle_text(keyparser, seq[-1])
        assert blocker.signal_triggered
        assert forward_partial_key.call_args_list == [
            ((str(keyutils.KeyInfo(key, Qt.KeyboardModifier.NoModifier)),),) for key in seq
        ]
        if hint_seq is not None:
            if len(seq) > len(hint_seq):
                assert hintmanager.keystr == 'z'
            else:
                assert hintmanager.keystr == hint_seq[:len(seq)]
        else:
            assert hintmanager.keystr == ''

    @pytest.mark.parametrize('seq, hint_seq, keystr', [
        ((Qt.Key.Key_F,), None, None),
        ((Qt.Key.Key_F,), 'f', None),
        ((Qt.Key.Key_F,), 'fz', None),
        ((Qt.Key.Key_F,), 'fzz', None),
        ((Qt.Key.Key_F,), 'fza', None),
        ((Qt.Key.Key_F, Qt.Key.Key_G), None, None),
        ((Qt.Key.Key_F, Qt.Key.Key_G), 'f', 'g'),
        ((Qt.Key.Key_F, Qt.Key.Key_G), 'fg', None),
        ((Qt.Key.Key_F, Qt.Key.Key_G), 'fgz', None),
        ((Qt.Key.Key_F, Qt.Key.Key_G), 'fgzz', None),
        ((Qt.Key.Key_F, Qt.Key.Key_G), 'fgza', None),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), None, None),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'f', 'gh'),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'fg', 'h'),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'fgh', None),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'fghz', None),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'fghzz', None),
        ((Qt.Key.Key_F, Qt.Key.Key_G, Qt.Key.Key_H), 'fghza', None),
    ])
    def test_forward_keys_partial(self, config_stub, handle_text, keyparser,
                                  qtbot, hintmanager, commandrunner, seq,
                                  hint_seq, keystr):
        command_parser = keyparser._command_parser
        config_stub.val.bindings.commands = {
            'hint': {
                'fy': 'message-info fy',
                'fgy': 'message-info fgy',
                'fghy': 'message-info fghy',
            }
        }
        if hint_seq is not None:
            keyparser.update_bindings([hint_seq, 'gh', 'h'])
        forward_partial_key = mock.Mock()
        command_parser.forward_partial_key.connect(forward_partial_key)
        handle_text(keyparser, *seq)
        assert not commandrunner.commands
        signals = [command_parser.forward_partial_key] * len(seq)
        with qtbot.wait_signals(signals) as blocker:
            handle_text(keyparser, Qt.Key.Key_F)
        assert blocker.signal_triggered
        assert forward_partial_key.call_args_list == [
            ((str(keyutils.KeyInfo(key, Qt.KeyboardModifier.NoModifier)),),) for key in seq
        ]
        assert command_parser._sequence == keyutils.KeySequence.parse('f')
        if hint_seq is not None:
            if keystr is not None:
                assert len(seq) > len(hint_seq)
                assert hintmanager.keystr == keystr
            else:
                assert hintmanager.keystr == hint_seq[:len(seq)]
        else:
            assert hintmanager.keystr == ''.join(
                str(keyutils.KeyInfo(key, Qt.KeyboardModifier.NoModifier)) for key in seq)

    @pytest.mark.parametrize('data_sequence', [
        ((Qt.Key.Key_A, 'timer_inactive'),),
        ((Qt.Key.Key_B, 'timer_active'),),
        ((Qt.Key.Key_C, 'timer_inactive'),),
        ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_A, 'timer_inactive'),),
        ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_B, 'timer_reset'),),
        ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_C, 'timer_inactive'),),
        ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_B, 'timer_reset'), (Qt.Key.Key_A, 'timer_inactive'),),
        ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_B, 'timer_reset'), (Qt.Key.Key_B, 'timer_reset'),),
        ((Qt.Key.Key_B, 'timer_active'), (Qt.Key.Key_B, 'timer_reset'), (Qt.Key.Key_C, 'timer_inactive'),),
    ])
    def test_partial_keychain_timeout(self, keyparser, config_stub, qtbot,
                                      hintmanager, commandrunner,
                                      data_sequence):
        """Test partial keychain timeout behavior."""
        command_parser = keyparser._command_parser
        config_stub.val.bindings.commands = {
            'hint': {
                'a': 'message-info a',
                'ba': 'message-info ba',
                'bba': 'message-info bba',
                'bbba': 'message-info bbba',
            }
        }
        keyparser.update_bindings(['bbb'])

        timeout = 100
        config_stub.val.input.partial_timeout = timeout
        timer = keyparser._partial_timer
        assert not timer.isActive()

        behavior = None
        for key, behavior in data_sequence:
            keyinfo = keyutils.KeyInfo(key, Qt.KeyboardModifier.NoModifier)
            if behavior == 'timer_active':
                # Timer should be active
                keyparser.handle(keyinfo.to_event())
                assert timer.isSingleShot()
                assert timer.interval() == timeout
                assert timer.isActive()
            elif behavior == 'timer_inactive':
                # Timer should be inactive
                keyparser.handle(keyinfo.to_event())
                assert not timer.isActive()
            elif behavior == 'timer_reset':
                # Timer should be reset after handling the key
                half_timer = QTimer()
                half_timer.setSingleShot(True)
                half_timer.setInterval(timeout//2)
                half_timer.start()
                # Simulate a half timeout to check for reset
                qtbot.wait_signal(half_timer.timeout).wait()
                assert (timeout - (timeout//4)) > timer.remainingTime()
                keyparser.handle(keyinfo.to_event())
                assert (timeout - (timeout//4)) < timer.remainingTime()
                assert timer.isActive()
            else:
                pytest.fail('Unreachable')
        if behavior in ['timer_active', 'timer_reset']:
            # Wait for the timer to timeout and check the keystring has been forwarded.
            # Only wait for up to 2*timeout, then raise an error.
            with qtbot.wait_signal(command_parser.keystring_updated,
                                   timeout=2*timeout) as blocker:
                pass
            assert blocker.args == ['']
            assert hintmanager.keystr == ('b' * len(data_sequence))
