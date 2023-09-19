# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for BaseKeyParser."""

import logging
import re
import sys
from unittest import mock

from qutebrowser.qt.core import Qt
import pytest

from qutebrowser.keyinput import basekeyparser, keyutils
from qutebrowser.utils import utils, usertypes


# Alias because we need this a lot in here.
def keyseq(s):
    return keyutils.KeySequence.parse(s)


def _create_keyparser(mode):
    kp = basekeyparser.BaseKeyParser(mode=mode, win_id=0)
    kp.execute = mock.Mock()
    return kp


@pytest.fixture
def keyparser(key_config_stub, keyinput_bindings):
    return _create_keyparser(usertypes.KeyMode.normal)


@pytest.fixture
def prompt_keyparser(key_config_stub, keyinput_bindings):
    return _create_keyparser(usertypes.KeyMode.prompt)


@pytest.fixture
def handle_text():
    """Helper function to handle multiple fake keypresses."""
    def func(kp, *args):
        for key in args:
            info = keyutils.KeyInfo(key, Qt.KeyboardModifier.NoModifier)
            kp.handle(info.to_event())
    return func


class TestDebugLog:

    """Make sure _debug_log only logs when do_log is set."""

    def test_log(self, keyparser, caplog):
        keyparser._debug_log('foo')
        assert caplog.messages == ['BaseKeyParser for mode normal: foo']

    def test_no_log(self, keyparser, caplog):
        keyparser._do_log = False
        keyparser._debug_log('foo')
        assert not caplog.records


@pytest.mark.parametrize('input_key, supports_count, count, command', [
    # (input_key, supports_count, expected)
    ('10', True, '10', ''),
    ('10g', True, '10', 'g'),
    ('10e4g', True, '4', 'g'),
    ('g', True, '', 'g'),
    ('0', True, '', ''),
    ('10g', False, '', 'g'),
])
def test_split_count(config_stub, key_config_stub,
                     input_key, supports_count, count, command):
    kp = basekeyparser.BaseKeyParser(mode=usertypes.KeyMode.normal, win_id=0,
                                     supports_count=supports_count)

    for info in keyseq(input_key):
        kp.handle(info.to_event())

    assert kp._count == count
    assert kp._sequence == keyseq(command)


def test_empty_binding(keyparser, config_stub):
    """Make sure setting an empty binding doesn't crash."""
    config_stub.val.bindings.commands = {'normal': {'co': ''}}
    # The config is re-read automatically


@pytest.mark.parametrize('changed_mode, expected', [
    ('normal', True), ('command', False),
])
def test_read_config(keyparser, key_config_stub, changed_mode, expected):
    keyparser._read_config()
    # Sanity checks
    assert keyseq('a') in keyparser.bindings
    assert keyseq('new') not in keyparser.bindings

    key_config_stub.bind(keyseq('new'), 'message-info new',
                         mode=changed_mode)

    assert keyseq('a') in keyparser.bindings
    assert (keyseq('new') in keyparser.bindings) == expected


class TestHandle:

    def test_valid_key(self, prompt_keyparser, handle_text):
        modifier = Qt.KeyboardModifier.MetaModifier if utils.is_mac else Qt.KeyboardModifier.ControlModifier

        infos = [
            keyutils.KeyInfo(Qt.Key.Key_A, modifier),
            keyutils.KeyInfo(Qt.Key.Key_X, modifier),
        ]
        for info in infos:
            prompt_keyparser.handle(info.to_event())

        prompt_keyparser.execute.assert_called_once_with(
            'message-info ctrla', None)
        assert not prompt_keyparser._sequence

    def test_valid_key_count(self, prompt_keyparser):
        modifier = Qt.KeyboardModifier.MetaModifier if utils.is_mac else Qt.KeyboardModifier.ControlModifier

        infos = [
            keyutils.KeyInfo(Qt.Key.Key_5, Qt.KeyboardModifier.NoModifier),
            keyutils.KeyInfo(Qt.Key.Key_A, modifier),
        ]
        for info in infos:
            prompt_keyparser.handle(info.to_event())
        prompt_keyparser.execute.assert_called_once_with(
            'message-info ctrla', 5)

    @pytest.mark.parametrize('keys', [
        [(Qt.Key.Key_B, Qt.KeyboardModifier.NoModifier), (Qt.Key.Key_C, Qt.KeyboardModifier.NoModifier)],
        [(Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)],
        # Only modifier
        [(Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier)],
    ])
    def test_invalid_keys(self, prompt_keyparser, keys):
        for key, modifiers in keys:
            info = keyutils.KeyInfo(key, modifiers)
            prompt_keyparser.handle(info.to_event())
        assert not prompt_keyparser.execute.called
        assert not prompt_keyparser._sequence

    def test_dry_run(self, prompt_keyparser):
        b_info = keyutils.KeyInfo(Qt.Key.Key_B, Qt.KeyboardModifier.NoModifier)
        prompt_keyparser.handle(b_info.to_event())

        a_info = keyutils.KeyInfo(Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
        prompt_keyparser.handle(a_info.to_event(), dry_run=True)

        assert not prompt_keyparser.execute.called
        assert prompt_keyparser._sequence

    def test_dry_run_count(self, prompt_keyparser):
        info = keyutils.KeyInfo(Qt.Key.Key_9, Qt.KeyboardModifier.NoModifier)
        prompt_keyparser.handle(info.to_event(), dry_run=True)
        assert not prompt_keyparser._count

    def test_invalid_key(self, prompt_keyparser):
        keys = [Qt.Key.Key_B, keyutils._NIL_KEY]
        for key in keys:
            info = keyutils.KeyInfo(key, Qt.KeyboardModifier.NoModifier)
            prompt_keyparser.handle(info.to_event())
        assert not prompt_keyparser._sequence

    def test_valid_keychain(self, handle_text, prompt_keyparser):
        handle_text(prompt_keyparser,
                    # Press 'x' which is ignored because of no match
                    Qt.Key.Key_X,
                    # Then start the real chain
                    Qt.Key.Key_B, Qt.Key.Key_A)
        prompt_keyparser.execute.assert_called_with('message-info ba', None)
        assert not prompt_keyparser._sequence

    @pytest.mark.parametrize('key, modifiers, number', [
        (Qt.Key.Key_0, Qt.KeyboardModifier.NoModifier, 0),
        (Qt.Key.Key_1, Qt.KeyboardModifier.NoModifier, 1),
        (Qt.Key.Key_1, Qt.KeyboardModifier.KeypadModifier, 1),
    ])
    def test_number_press(self, prompt_keyparser,
                          key, modifiers, number):
        prompt_keyparser.handle(keyutils.KeyInfo(key, modifiers).to_event())
        command = 'message-info {}'.format(number)
        prompt_keyparser.execute.assert_called_once_with(command, None)
        assert not prompt_keyparser._sequence

    @pytest.mark.parametrize('modifiers, text', [
        (Qt.KeyboardModifier.NoModifier, '2'),
        (Qt.KeyboardModifier.KeypadModifier, 'num-2'),
    ])
    def test_number_press_keypad(self, keyparser, config_stub,
                                 modifiers, text):
        """Make sure a <Num+2> binding overrides the 2 binding."""
        config_stub.val.bindings.commands = {'normal': {
            '2': 'message-info 2',
            '<Num+2>': 'message-info num-2'}}
        keyparser.handle(keyutils.KeyInfo(Qt.Key.Key_2, modifiers).to_event())
        command = 'message-info {}'.format(text)
        keyparser.execute.assert_called_once_with(command, None)
        assert not keyparser._sequence

    def test_umlauts(self, handle_text, keyparser, config_stub):
        config_stub.val.bindings.commands = {'normal': {'ü': 'message-info ü'}}
        handle_text(keyparser, Qt.Key.Key_Udiaeresis)
        keyparser.execute.assert_called_once_with('message-info ü', None)

    def test_mapping(self, config_stub, handle_text, prompt_keyparser):
        handle_text(prompt_keyparser, Qt.Key.Key_X)
        prompt_keyparser.execute.assert_called_once_with(
            'message-info a', None)

    def test_mapping_keypad(self, config_stub, keyparser):
        """Make sure falling back to non-numpad keys works with mappings."""
        config_stub.val.bindings.commands = {'normal': {'a': 'nop'}}
        config_stub.val.bindings.key_mappings = {'1': 'a'}

        info = keyutils.KeyInfo(Qt.Key.Key_1, Qt.KeyboardModifier.KeypadModifier)
        keyparser.handle(info.to_event())
        keyparser.execute.assert_called_once_with('nop', None)

    def test_binding_and_mapping(self, config_stub, handle_text, prompt_keyparser):
        """with a conflicting binding/mapping, the binding should win."""
        handle_text(prompt_keyparser, Qt.Key.Key_B)
        assert not prompt_keyparser.execute.called

    def test_mapping_in_key_chain(self, config_stub, handle_text, keyparser):
        """A mapping should work even as part of a keychain."""
        config_stub.val.bindings.commands = {'normal':
                                             {'aa': 'message-info aa'}}
        handle_text(keyparser, Qt.Key.Key_A, Qt.Key.Key_X)
        keyparser.execute.assert_called_once_with('message-info aa', None)

    def test_binding_with_shift(self, prompt_keyparser):
        """Simulate a binding which involves shift."""
        for key, modifiers in [(Qt.Key.Key_Y, Qt.KeyboardModifier.NoModifier),
                               (Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier),
                               (Qt.Key.Key_Y, Qt.KeyboardModifier.ShiftModifier)]:
            info = keyutils.KeyInfo(key, modifiers)
            prompt_keyparser.handle(info.to_event())

        prompt_keyparser.execute.assert_called_once_with('yank -s', None)

    def test_partial_before_full_match(self, keyparser, config_stub):
        """Make sure full matches always take precedence over partial ones."""
        config_stub.val.bindings.commands = {
            'normal': {
                'ab': 'message-info bar',
                'a': 'message-info foo'
            }
        }
        info = keyutils.KeyInfo(Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
        keyparser.handle(info.to_event())
        keyparser.execute.assert_called_once_with('message-info foo', None)


class TestCount:

    """Test execute() with counts."""

    def test_no_count(self, handle_text, prompt_keyparser):
        """Test with no count added."""
        handle_text(prompt_keyparser, Qt.Key.Key_B, Qt.Key.Key_A)
        prompt_keyparser.execute.assert_called_once_with(
            'message-info ba', None)
        assert not prompt_keyparser._sequence

    def test_count_0(self, handle_text, prompt_keyparser):
        handle_text(prompt_keyparser, Qt.Key.Key_0, Qt.Key.Key_B, Qt.Key.Key_A)
        calls = [mock.call('message-info 0', None),
                 mock.call('message-info ba', None)]
        prompt_keyparser.execute.assert_has_calls(calls)
        assert not prompt_keyparser._sequence

    def test_count_42(self, handle_text, prompt_keyparser):
        handle_text(prompt_keyparser, Qt.Key.Key_4, Qt.Key.Key_2, Qt.Key.Key_B, Qt.Key.Key_A)
        prompt_keyparser.execute.assert_called_once_with('message-info ba', 42)
        assert not prompt_keyparser._sequence

    def test_count_42_invalid(self, handle_text, prompt_keyparser):
        # Invalid call with ccx gets ignored
        handle_text(prompt_keyparser,
                    Qt.Key.Key_4, Qt.Key.Key_2, Qt.Key.Key_C, Qt.Key.Key_C, Qt.Key.Key_X)
        assert not prompt_keyparser.execute.called
        assert not prompt_keyparser._sequence
        # Valid call with ccc gets the correct count
        handle_text(prompt_keyparser,
                    Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_C, Qt.Key.Key_C, Qt.Key.Key_C)
        prompt_keyparser.execute.assert_called_once_with(
            'message-info ccc', 23)
        assert not prompt_keyparser._sequence

    def test_superscript(self, handle_text, prompt_keyparser):
        # https://github.com/qutebrowser/qutebrowser/issues/3743
        handle_text(prompt_keyparser, Qt.Key.Key_twosuperior, Qt.Key.Key_B, Qt.Key.Key_A)

    def test_count_keystring_update(self, qtbot,
                                    handle_text, prompt_keyparser):
        """Make sure the keystring is updated correctly when entering count."""
        with qtbot.wait_signals([
                prompt_keyparser.keystring_updated,
                prompt_keyparser.keystring_updated]) as blocker:
            handle_text(prompt_keyparser, Qt.Key.Key_4, Qt.Key.Key_2)
        sig1, sig2 = blocker.all_signals_and_args
        assert sig1.args == ('4',)
        assert sig2.args == ('42',)

    def test_numpad(self, prompt_keyparser):
        """Make sure we can enter a count via numpad."""
        for key, modifiers in [(Qt.Key.Key_4, Qt.KeyboardModifier.KeypadModifier),
                               (Qt.Key.Key_2, Qt.KeyboardModifier.KeypadModifier),
                               (Qt.Key.Key_B, Qt.KeyboardModifier.NoModifier),
                               (Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)]:
            info = keyutils.KeyInfo(key, modifiers)
            prompt_keyparser.handle(info.to_event())
        prompt_keyparser.execute.assert_called_once_with('message-info ba', 42)


def test_clear_keystring(qtbot, keyparser):
    """Test that the keystring is cleared and the signal is emitted."""
    keyparser._sequence = keyseq('test')
    keyparser._count = '23'
    with qtbot.wait_signal(keyparser.keystring_updated):
        keyparser.clear_keystring()
    assert not keyparser._sequence
    assert not keyparser._count


def test_clear_keystring_empty(qtbot, keyparser):
    """Test that no signal is emitted when clearing an empty keystring.."""
    keyparser._sequence = keyseq('')
    with qtbot.assert_not_emitted(keyparser.keystring_updated):
        keyparser.clear_keystring()


def test_respect_config_when_matching_counts(keyparser, config_stub):
    """Don't match counts if disabled in the config."""
    config_stub.val.input.match_counts = False

    info = keyutils.KeyInfo(Qt.Key.Key_1, Qt.KeyboardModifier.NoModifier)
    keyparser.handle(info.to_event())

    assert not keyparser._sequence
    assert not keyparser._count


def test_count_limit_exceeded(handle_text, keyparser, caplog):
    try:
        max_digits = sys.get_int_max_str_digits()
    except AttributeError:
        pytest.skip('sys.get_int_max_str_digits() not available')

    keys = (max_digits + 1) * [Qt.Key.Key_1]

    with caplog.at_level(logging.ERROR):
        handle_text(keyparser, *keys, Qt.Key.Key_B, Qt.Key.Key_A)

    pattern = re.compile(r"^Failed to parse count: Exceeds the limit .* for integer string conversion: .*")
    assert any(pattern.fullmatch(msg) for msg in caplog.messages)
    assert not keyparser._sequence
    assert not keyparser._count
