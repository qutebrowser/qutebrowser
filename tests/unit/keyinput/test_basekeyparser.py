# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
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

"""Tests for BaseKeyParser."""

from unittest import mock

from PyQt5.QtCore import Qt
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
def handle_text(fake_keyevent):
    """Helper function to handle multiple fake keypresses."""
    def func(kp, *args):
        for enumval in args:
            kp.handle(fake_keyevent(enumval))
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

    def test_valid_key(self, fake_keyevent, prompt_keyparser):
        modifier = Qt.MetaModifier if utils.is_mac else Qt.ControlModifier
        prompt_keyparser.handle(fake_keyevent(Qt.Key_A, modifier))
        prompt_keyparser.handle(fake_keyevent(Qt.Key_X, modifier))
        prompt_keyparser.execute.assert_called_once_with(
            'message-info ctrla', None)
        assert not prompt_keyparser._sequence

    def test_valid_key_count(self, fake_keyevent, prompt_keyparser):
        modifier = Qt.MetaModifier if utils.is_mac else Qt.ControlModifier
        prompt_keyparser.handle(fake_keyevent(Qt.Key_5))
        prompt_keyparser.handle(fake_keyevent(Qt.Key_A, modifier))
        prompt_keyparser.execute.assert_called_once_with(
            'message-info ctrla', 5)

    @pytest.mark.parametrize('keys', [
        [(Qt.Key_B, Qt.NoModifier), (Qt.Key_C, Qt.NoModifier)],
        [(Qt.Key_A, Qt.ControlModifier | Qt.AltModifier)],
        # Only modifier
        [(Qt.Key_Shift, Qt.ShiftModifier)],
    ])
    def test_invalid_keys(self, fake_keyevent, prompt_keyparser, keys):
        for key, modifiers in keys:
            prompt_keyparser.handle(fake_keyevent(key, modifiers))
        assert not prompt_keyparser.execute.called
        assert not prompt_keyparser._sequence

    def test_dry_run(self, fake_keyevent, prompt_keyparser):
        prompt_keyparser.handle(fake_keyevent(Qt.Key_B))
        prompt_keyparser.handle(fake_keyevent(Qt.Key_A), dry_run=True)
        assert not prompt_keyparser.execute.called
        assert prompt_keyparser._sequence

    def test_dry_run_count(self, fake_keyevent, prompt_keyparser):
        prompt_keyparser.handle(fake_keyevent(Qt.Key_9), dry_run=True)
        assert not prompt_keyparser._count

    def test_invalid_key(self, fake_keyevent, prompt_keyparser):
        prompt_keyparser.handle(fake_keyevent(Qt.Key_B))
        prompt_keyparser.handle(fake_keyevent(0x0))
        assert not prompt_keyparser._sequence

    def test_valid_keychain(self, handle_text, prompt_keyparser):
        handle_text(prompt_keyparser,
                    # Press 'x' which is ignored because of no match
                    Qt.Key_X,
                    # Then start the real chain
                    Qt.Key_B, Qt.Key_A)
        prompt_keyparser.execute.assert_called_with('message-info ba', None)
        assert not prompt_keyparser._sequence

    @pytest.mark.parametrize('key, modifiers, number', [
        (Qt.Key_0, Qt.NoModifier, 0),
        (Qt.Key_1, Qt.NoModifier, 1),
        (Qt.Key_1, Qt.KeypadModifier, 1),
    ])
    def test_number_press(self, fake_keyevent, prompt_keyparser,
                          key, modifiers, number):
        prompt_keyparser.handle(fake_keyevent(key, modifiers))
        command = 'message-info {}'.format(number)
        prompt_keyparser.execute.assert_called_once_with(command, None)
        assert not prompt_keyparser._sequence

    @pytest.mark.parametrize('modifiers, text', [
        (Qt.NoModifier, '2'),
        (Qt.KeypadModifier, 'num-2'),
    ])
    def test_number_press_keypad(self, fake_keyevent, keyparser, config_stub,
                                 modifiers, text):
        """Make sure a <Num+2> binding overrides the 2 binding."""
        config_stub.val.bindings.commands = {'normal': {
            '2': 'message-info 2',
            '<Num+2>': 'message-info num-2'}}
        keyparser.handle(fake_keyevent(Qt.Key_2, modifiers))
        command = 'message-info {}'.format(text)
        keyparser.execute.assert_called_once_with(command, None)
        assert not keyparser._sequence

    def test_umlauts(self, handle_text, keyparser, config_stub):
        config_stub.val.bindings.commands = {'normal': {'ü': 'message-info ü'}}
        handle_text(keyparser, Qt.Key_Udiaeresis)
        keyparser.execute.assert_called_once_with('message-info ü', None)

    def test_mapping(self, config_stub, handle_text, prompt_keyparser):
        handle_text(prompt_keyparser, Qt.Key_X)
        prompt_keyparser.execute.assert_called_once_with(
            'message-info a', None)

    def test_mapping_keypad(self, config_stub, fake_keyevent, keyparser):
        """Make sure falling back to non-numpad keys works with mappings."""
        config_stub.val.bindings.commands = {'normal': {'a': 'nop'}}
        config_stub.val.bindings.key_mappings = {'1': 'a'}

        keyparser.handle(fake_keyevent(Qt.Key_1, Qt.KeypadModifier))
        keyparser.execute.assert_called_once_with('nop', None)

    def test_binding_and_mapping(self, config_stub, handle_text, prompt_keyparser):
        """with a conflicting binding/mapping, the binding should win."""
        handle_text(prompt_keyparser, Qt.Key_B)
        assert not prompt_keyparser.execute.called

    def test_mapping_in_key_chain(self, config_stub, handle_text, keyparser):
        """A mapping should work even as part of a keychain."""
        config_stub.val.bindings.commands = {'normal':
                                             {'aa': 'message-info aa'}}
        handle_text(keyparser, Qt.Key_A, Qt.Key_X)
        keyparser.execute.assert_called_once_with('message-info aa', None)

    def test_binding_with_shift(self, prompt_keyparser, fake_keyevent):
        """Simulate a binding which involves shift."""
        for key, modifiers in [(Qt.Key_Y, Qt.NoModifier),
                               (Qt.Key_Shift, Qt.ShiftModifier),
                               (Qt.Key_Y, Qt.ShiftModifier)]:
            prompt_keyparser.handle(fake_keyevent(key, modifiers))

        prompt_keyparser.execute.assert_called_once_with('yank -s', None)

    def test_partial_before_full_match(self, keyparser, fake_keyevent,
                                       config_stub):
        """Make sure full matches always take precedence over partial ones."""
        config_stub.val.bindings.commands = {
            'normal': {
                'ab': 'message-info bar',
                'a': 'message-info foo'
            }
        }
        keyparser.handle(fake_keyevent(Qt.Key_A))
        keyparser.execute.assert_called_once_with('message-info foo', None)


class TestCount:

    """Test execute() with counts."""

    def test_no_count(self, handle_text, prompt_keyparser):
        """Test with no count added."""
        handle_text(prompt_keyparser, Qt.Key_B, Qt.Key_A)
        prompt_keyparser.execute.assert_called_once_with(
            'message-info ba', None)
        assert not prompt_keyparser._sequence

    def test_count_0(self, handle_text, prompt_keyparser):
        handle_text(prompt_keyparser, Qt.Key_0, Qt.Key_B, Qt.Key_A)
        calls = [mock.call('message-info 0', None),
                 mock.call('message-info ba', None)]
        prompt_keyparser.execute.assert_has_calls(calls)
        assert not prompt_keyparser._sequence

    def test_count_42(self, handle_text, prompt_keyparser):
        handle_text(prompt_keyparser, Qt.Key_4, Qt.Key_2, Qt.Key_B, Qt.Key_A)
        prompt_keyparser.execute.assert_called_once_with('message-info ba', 42)
        assert not prompt_keyparser._sequence

    def test_count_42_invalid(self, handle_text, prompt_keyparser):
        # Invalid call with ccx gets ignored
        handle_text(prompt_keyparser,
                    Qt.Key_4, Qt.Key_2, Qt.Key_C, Qt.Key_C, Qt.Key_X)
        assert not prompt_keyparser.execute.called
        assert not prompt_keyparser._sequence
        # Valid call with ccc gets the correct count
        handle_text(prompt_keyparser,
                    Qt.Key_2, Qt.Key_3, Qt.Key_C, Qt.Key_C, Qt.Key_C)
        prompt_keyparser.execute.assert_called_once_with(
            'message-info ccc', 23)
        assert not prompt_keyparser._sequence

    def test_superscript(self, handle_text, prompt_keyparser):
        # https://github.com/qutebrowser/qutebrowser/issues/3743
        handle_text(prompt_keyparser, Qt.Key_twosuperior, Qt.Key_B, Qt.Key_A)

    def test_count_keystring_update(self, qtbot,
                                    handle_text, prompt_keyparser):
        """Make sure the keystring is updated correctly when entering count."""
        with qtbot.waitSignals([
                prompt_keyparser.keystring_updated,
                prompt_keyparser.keystring_updated]) as blocker:
            handle_text(prompt_keyparser, Qt.Key_4, Qt.Key_2)
        sig1, sig2 = blocker.all_signals_and_args
        assert sig1.args == ('4',)
        assert sig2.args == ('42',)

    def test_numpad(self, fake_keyevent, prompt_keyparser):
        """Make sure we can enter a count via numpad."""
        for key, modifiers in [(Qt.Key_4, Qt.KeypadModifier),
                               (Qt.Key_2, Qt.KeypadModifier),
                               (Qt.Key_B, Qt.NoModifier),
                               (Qt.Key_A, Qt.NoModifier)]:
            prompt_keyparser.handle(fake_keyevent(key, modifiers))
        prompt_keyparser.execute.assert_called_once_with('message-info ba', 42)


def test_clear_keystring(qtbot, keyparser):
    """Test that the keystring is cleared and the signal is emitted."""
    keyparser._sequence = keyseq('test')
    keyparser._count = '23'
    with qtbot.waitSignal(keyparser.keystring_updated):
        keyparser.clear_keystring()
    assert not keyparser._sequence
    assert not keyparser._count


def test_clear_keystring_empty(qtbot, keyparser):
    """Test that no signal is emitted when clearing an empty keystring.."""
    keyparser._sequence = keyseq('')
    with qtbot.assert_not_emitted(keyparser.keystring_updated):
        keyparser.clear_keystring()
