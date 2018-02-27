# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
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
from qutebrowser.utils import utils


# Alias because we need this a lot in here.
def keyseq(s):
    return keyutils.KeySequence.parse(s)


@pytest.fixture
def keyparser(key_config_stub):
    """Fixture providing a BaseKeyParser supporting count/chains."""
    kp = basekeyparser.BaseKeyParser(0, supports_count=True)
    kp.execute = mock.Mock()
    yield kp


@pytest.fixture
def handle_text(fake_keyevent_factory, keyparser):
    """Helper function to handle multiple fake keypresses.

    Automatically uses the keyparser of the current test via the keyparser
    fixture.
    """
    def func(*args):
        for enumval, text in args:
            keyparser.handle(fake_keyevent_factory(enumval, text=text))
    return func


class TestDebugLog:

    """Make sure _debug_log only logs when do_log is set."""

    def test_log(self, keyparser, caplog):
        keyparser._debug_log('foo')
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.message == 'foo'

    def test_no_log(self, keyparser, caplog):
        keyparser.do_log = False
        keyparser._debug_log('foo')
        assert not caplog.records


@pytest.mark.parametrize('input_key, supports_count, count, command', [
    # (input_key, supports_count, expected)
    ('10', True, '10', ''),
    ('10g', True, '10', 'g'),
    ('10e4g', True, '4', 'g'),
    ('g', True, '', 'g'),
    ('10g', False, '', 'g'),
])
def test_split_count(config_stub, key_config_stub,
                     input_key, supports_count, count, command):
    kp = basekeyparser.BaseKeyParser(0, supports_count=supports_count)
    kp._read_config('normal')

    for info in keyseq(input_key):
        kp.handle(info.to_event())

    assert kp._count == count
    assert kp._sequence == keyseq(command)


@pytest.mark.usefixtures('keyinput_bindings')
class TestReadConfig:

    def test_read_config_invalid(self, keyparser):
        """Test reading config without setting modename before."""
        with pytest.raises(ValueError):
            keyparser._read_config()

    def test_read_config_modename(self, keyparser):
        """Test reading config with _modename set."""
        keyparser._modename = 'normal'
        keyparser._read_config()
        assert keyseq('a') in keyparser.bindings

    def test_read_config_valid(self, keyparser):
        """Test reading config."""
        keyparser._read_config('prompt')
        assert keyseq('ccc') in keyparser.bindings
        assert keyseq('<ctrl+a>') in keyparser.bindings
        keyparser._read_config('command')
        assert keyseq('ccc') not in keyparser.bindings
        assert keyseq('<ctrl+a>') not in keyparser.bindings
        assert keyseq('foo') in keyparser.bindings
        assert keyseq('<ctrl+x>') in keyparser.bindings

    def test_read_config_modename_none(self, keyparser):
        assert keyparser._modename is None

        # No config set so self._modename is None
        with pytest.raises(ValueError, match="read_config called with no mode "
                           "given, but None defined so far!"):
            keyparser._read_config(None)

    @pytest.mark.parametrize('mode, changed_mode, expected', [
        ('normal', 'normal', True), ('normal', 'command', False),
    ])
    def test_read_config(self, keyparser, key_config_stub,
                         mode, changed_mode, expected):
        keyparser._read_config(mode)
        # Sanity checks
        assert keyseq('a') in keyparser.bindings
        assert keyseq('new') not in keyparser.bindings

        key_config_stub.bind(keyseq('new'), 'message-info new',
                             mode=changed_mode)

        assert keyseq('a') in keyparser.bindings
        assert (keyseq('new') in keyparser.bindings) == expected


class TestSpecialKeys:

    """Check execute() with special keys."""

    @pytest.fixture(autouse=True)
    def read_config(self, keyinput_bindings, keyparser):
        keyparser._read_config('prompt')

    def test_valid_key(self, fake_keyevent_factory, keyparser):
        modifier = Qt.MetaModifier if utils.is_mac else Qt.ControlModifier
        keyparser.handle(fake_keyevent_factory(Qt.Key_A, modifier))
        keyparser.handle(fake_keyevent_factory(Qt.Key_X, modifier))
        keyparser.execute.assert_called_once_with('message-info ctrla', None)

    def test_valid_key_count(self, fake_keyevent_factory, keyparser):
        modifier = Qt.MetaModifier if utils.is_mac else Qt.ControlModifier
        keyparser.handle(fake_keyevent_factory(Qt.Key_5, text='5'))
        keyparser.handle(fake_keyevent_factory(Qt.Key_A, modifier, text='A'))
        keyparser.execute.assert_called_once_with('message-info ctrla', 5)

    def test_invalid_key(self, fake_keyevent_factory, keyparser):
        keyparser.handle(fake_keyevent_factory(
            Qt.Key_A, (Qt.ControlModifier | Qt.AltModifier)))
        assert not keyparser.execute.called

    @pytest.mark.skip(reason='unneeded?')
    def test_keychain(self, fake_keyevent_factory, keyparser):
        keyparser.handle(fake_keyevent_factory(Qt.Key_B))
        keyparser.handle(fake_keyevent_factory(Qt.Key_A))
        assert not keyparser.execute.called

    def test_no_binding(self, monkeypatch, fake_keyevent_factory, keyparser):
        monkeypatch.setattr(keyutils.KeyInfo, '__str__', lambda _self: '')
        keyparser.handle(fake_keyevent_factory(Qt.Key_A, Qt.NoModifier))
        assert not keyparser.execute.called

    def test_mapping(self, config_stub, fake_keyevent_factory, keyparser):
        modifier = Qt.MetaModifier if utils.is_mac else Qt.ControlModifier

        keyparser.handle(fake_keyevent_factory(Qt.Key_B, modifier))
        keyparser.execute.assert_called_once_with('message-info ctrla', None)

    def test_binding_and_mapping(self, config_stub, fake_keyevent_factory,
                                 keyparser):
        """with a conflicting binding/mapping, the binding should win."""
        modifier = Qt.MetaModifier if utils.is_mac else Qt.ControlModifier

        keyparser.handle(fake_keyevent_factory(Qt.Key_A, modifier))
        keyparser.execute.assert_called_once_with('message-info ctrla', None)


class TestKeyChain:

    """Test execute() with keychain support."""

    @pytest.fixture(autouse=True)
    def read_config(self, keyinput_bindings, keyparser):
        keyparser._read_config('prompt')

    def test_valid_special_key(self, fake_keyevent_factory, keyparser):
        if utils.is_mac:
            modifier = Qt.MetaModifier
        else:
            modifier = Qt.ControlModifier
        keyparser.handle(fake_keyevent_factory(Qt.Key_A, modifier))
        keyparser.handle(fake_keyevent_factory(Qt.Key_X, modifier))
        keyparser.execute.assert_called_once_with('message-info ctrla', None)
        assert not keyparser._sequence

    def test_invalid_special_key(self, fake_keyevent_factory, keyparser):
        keyparser.handle(fake_keyevent_factory(
            Qt.Key_A, (Qt.ControlModifier | Qt.AltModifier)))
        assert not keyparser.execute.called
        assert not keyparser._sequence

    def test_valid_keychain(self, handle_text, keyparser):
        # Press 'x' which is ignored because of no match
        handle_text((Qt.Key_X, 'x'),
                    # Then start the real chain
                    (Qt.Key_B, 'b'), (Qt.Key_A, 'a'))
        keyparser.execute.assert_called_with('message-info ba', None)
        assert not keyparser._sequence

    def test_0_press(self, handle_text, keyparser):
        handle_text((Qt.Key_0, '0'))
        keyparser.execute.assert_called_once_with('message-info 0', None)
        assert not keyparser._sequence

    def test_ambiguous_keychain(self, handle_text, keyparser):
        handle_text((Qt.Key_A, 'a'))
        assert keyparser.execute.called

    def test_invalid_keychain(self, handle_text, keyparser):
        handle_text((Qt.Key_B, 'b'))
        handle_text((Qt.Key_C, 'c'))
        assert not keyparser._sequence

    def test_mapping(self, config_stub, handle_text, keyparser):
        handle_text((Qt.Key_X, 'x'))
        keyparser.execute.assert_called_once_with('message-info a', None)

    def test_binding_and_mapping(self, config_stub, handle_text, keyparser):
        """with a conflicting binding/mapping, the binding should win."""
        handle_text((Qt.Key_B, 'b'))
        assert not keyparser.execute.called


class TestCount:

    """Test execute() with counts."""

    @pytest.fixture(autouse=True)
    def read_keyparser_config(self, keyinput_bindings, keyparser):
        keyparser._read_config('prompt')

    def test_no_count(self, handle_text, keyparser):
        """Test with no count added."""
        handle_text((Qt.Key_B, 'b'), (Qt.Key_A, 'a'))
        keyparser.execute.assert_called_once_with('message-info ba', None)
        assert not keyparser._sequence

    def test_count_0(self, handle_text, keyparser):
        handle_text((Qt.Key_0, '0'), (Qt.Key_B, 'b'), (Qt.Key_A, 'a'))
        calls = [mock.call('message-info 0', None),
                 mock.call('message-info ba', None)]
        keyparser.execute.assert_has_calls(calls)
        assert not keyparser._sequence

    def test_count_42(self, handle_text, keyparser):
        handle_text((Qt.Key_4, '4'), (Qt.Key_2, '2'), (Qt.Key_B, 'b'),
                    (Qt.Key_A, 'a'))
        keyparser.execute.assert_called_once_with('message-info ba', 42)
        assert not keyparser._sequence

    def test_count_42_invalid(self, handle_text, keyparser):
        # Invalid call with ccx gets ignored
        handle_text((Qt.Key_4, '4'), (Qt.Key_2, '2'), (Qt.Key_C, 'c'),
                    (Qt.Key_C, 'c'), (Qt.Key_X, 'x'))
        assert not keyparser.execute.called
        assert not keyparser._sequence
        # Valid call with ccc gets the correct count
        handle_text((Qt.Key_2, '2'), (Qt.Key_3, '3'), (Qt.Key_C, 'c'),
                    (Qt.Key_C, 'c'), (Qt.Key_C, 'c'))
        keyparser.execute.assert_called_once_with('message-info ccc', 23)
        assert not keyparser._sequence


def test_clear_keystring(qtbot, keyparser):
    """Test that the keystring is cleared and the signal is emitted."""
    keyparser._sequence = keyseq('test')
    with qtbot.waitSignal(keyparser.keystring_updated):
        keyparser.clear_keystring()
    assert not keyparser._sequence
