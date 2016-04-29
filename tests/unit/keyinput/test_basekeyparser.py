# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
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

import sys
import logging
from unittest import mock

from PyQt5.QtCore import Qt
import pytest

from qutebrowser.keyinput import basekeyparser
from qutebrowser.utils import utils


CONFIG = {'input': {'timeout': 100}}


@pytest.yield_fixture
def keyparser():
    """Fixture providing a BaseKeyParser supporting count/chains."""
    kp = basekeyparser.BaseKeyParser(
        0, supports_count=True, supports_chains=True)
    kp.execute = mock.Mock()
    yield kp
    assert not kp._ambiguous_timer.isActive()


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


@pytest.mark.parametrize('count, chains, count_expected, chains_expected', [
    (True, False, True, False),
    (False, True, False, True),
    (None, True, True, True),
])
def test_supports_args(count, chains, count_expected, chains_expected):
    kp = basekeyparser.BaseKeyParser(
        0, supports_count=count, supports_chains=chains)
    assert kp._supports_count == count_expected
    assert kp._supports_chains == chains_expected


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


@pytest.mark.parametrize('input_key, supports_count, expected', [
    # (input_key, supports_count, expected)
    ('10', True, (10, '')),
    ('10foo', True, (10, 'foo')),
    ('-1foo', True, (None, '-1foo')),
    ('10e4foo', True, (10, 'e4foo')),
    ('foo', True, (None, 'foo')),
    ('10foo', False, (None, '10foo')),
])
def test_split_count(input_key, supports_count, expected):
    kp = basekeyparser.BaseKeyParser(0, supports_count=supports_count)
    kp._keystring = input_key
    assert kp._split_count() == expected


@pytest.mark.usefixtures('fake_keyconfig')
class TestReadConfig:

    def test_read_config_invalid(self, keyparser):
        """Test reading config without setting modename before."""
        with pytest.raises(ValueError):
            keyparser.read_config()

    def test_read_config_modename(self, keyparser):
        """Test reading config with _modename set."""
        keyparser._modename = 'normal'
        keyparser.read_config()
        assert 'a' in keyparser.bindings

    def test_read_config_valid(self, keyparser):
        """Test reading config."""
        keyparser.read_config('test')
        assert 'ccc' in keyparser.bindings
        assert 'ctrl+a' in keyparser.special_bindings
        keyparser.read_config('test2')
        assert 'ccc' not in keyparser.bindings
        assert 'ctrl+a' not in keyparser.special_bindings
        assert 'foo' in keyparser.bindings
        assert 'ctrl+x' in keyparser.special_bindings

    def test_on_keyconfig_changed_modename_none(self, keyparser):
        assert keyparser._modename is None

        # No config set so self._modename is None
        with pytest.raises(AssertionError) as excinfo:
            keyparser.on_keyconfig_changed('normal')

        expected_text = "on_keyconfig_changed called but no section defined!"
        assert str(excinfo.value) == expected_text

    @pytest.mark.parametrize('mode,changed_mode, expected', [
        ('normal', 'normal', True), ('normal', 'normal2', False),
    ])
    def test_on_keyconfig_changed(self, keyparser, fake_keyconfig, mode,
                                  changed_mode, expected):
        keyparser.read_config(mode)
        # Sanity checks
        assert 'a' in keyparser.bindings
        assert 'new' not in keyparser.bindings

        fake_keyconfig['normal'] = {'new': 'new'}
        keyparser.on_keyconfig_changed(changed_mode)

        if expected:
            assert 'a' not in keyparser.bindings
            assert 'new' in keyparser.bindings
        else:
            assert 'a' in keyparser.bindings
            assert 'new' not in keyparser.bindings

    @pytest.mark.parametrize('warn_on_keychains', [True, False])
    def test_warn_on_keychains(self, caplog, warn_on_keychains):
        """Test _warn_on_keychains."""
        kp = basekeyparser.BaseKeyParser(
            0, supports_count=False, supports_chains=False)
        kp._warn_on_keychains = warn_on_keychains

        with caplog.at_level(logging.WARNING):
            kp.read_config('normal')

        assert bool(caplog.records) == warn_on_keychains


class TestSpecialKeys:

    """Check execute() with special keys."""

    @pytest.fixture(autouse=True)
    def read_config(self, fake_keyconfig, keyparser):
        keyparser.read_config('test')

    def test_valid_key(self, fake_keyevent_factory, keyparser):
        if sys.platform == 'darwin':
            modifier = Qt.MetaModifier
        else:
            modifier = Qt.ControlModifier
        keyparser.handle(fake_keyevent_factory(Qt.Key_A, modifier))
        keyparser.handle(fake_keyevent_factory(Qt.Key_X, modifier))
        keyparser.execute.assert_called_once_with(
            'ctrla', keyparser.Type.special)

    def test_invalid_key(self, fake_keyevent_factory, keyparser):
        keyparser.handle(fake_keyevent_factory(
            Qt.Key_A, (Qt.ControlModifier | Qt.AltModifier)))
        assert not keyparser.execute.called

    def test_keychain(self, fake_keyevent_factory, keyparser):
        keyparser.handle(fake_keyevent_factory(Qt.Key_B))
        keyparser.handle(fake_keyevent_factory(Qt.Key_A))
        assert not keyparser.execute.called

    def test_no_binding(self, monkeypatch, fake_keyevent_factory, keyparser):
        monkeypatch.setattr(utils, 'keyevent_to_string', lambda binding: None)
        keyparser.handle(fake_keyevent_factory(Qt.Key_A, Qt.NoModifier))
        assert not keyparser.execute.called


class TestKeyChain:

    """Test execute() with keychain support."""

    @pytest.fixture(autouse=True)
    def read_config(self, fake_keyconfig, keyparser):
        keyparser.read_config('test')

    def test_valid_special_key(self, fake_keyevent_factory, keyparser):
        if sys.platform == 'darwin':
            modifier = Qt.MetaModifier
        else:
            modifier = Qt.ControlModifier
        keyparser.handle(fake_keyevent_factory(Qt.Key_A, modifier))
        keyparser.handle(fake_keyevent_factory(Qt.Key_X, modifier))
        keyparser.execute.assert_called_once_with(
            'ctrla', keyparser.Type.special)
        assert keyparser._keystring == ''

    def test_invalid_special_key(self, fake_keyevent_factory, keyparser):
        keyparser.handle(fake_keyevent_factory(
            Qt.Key_A, (Qt.ControlModifier | Qt.AltModifier)))
        assert not keyparser.execute.called
        assert keyparser._keystring == ''

    def test_valid_keychain(self, handle_text, keyparser):
        # Press 'x' which is ignored because of no match
        handle_text((Qt.Key_X, 'x'),
                    # Then start the real chain
                    (Qt.Key_B, 'b'), (Qt.Key_A, 'a'))
        keyparser.execute.assert_called_once_with(
            'ba', keyparser.Type.chain, None)
        assert keyparser._keystring == ''

    def test_0_press(self, handle_text, keyparser):
        handle_text((Qt.Key_0, '0'))
        keyparser.execute.assert_called_once_with(
            '0', keyparser.Type.chain, None)
        assert keyparser._keystring == ''

    def test_ambiguous_keychain(self, qapp, handle_text, config_stub,
                                keyparser):
        config_stub.data = CONFIG
        timer = keyparser._ambiguous_timer
        assert not timer.isActive()
        # We start with 'a' where the keychain gives us an ambiguous result.
        # Then we check if the timer has been set up correctly
        handle_text((Qt.Key_A, 'a'))
        assert not keyparser.execute.called
        assert timer.isSingleShot()
        assert timer.interval() == 100
        assert timer.isActive()
        # Now we type an 'x' and check 'ax' has been executed and the timer
        # stopped.
        handle_text((Qt.Key_X, 'x'))
        keyparser.execute.assert_called_once_with(
            'ax', keyparser.Type.chain, None)
        assert not timer.isActive()
        assert keyparser._keystring == ''

    def test_ambiguous_keychain_no_timeout(self, handle_text, config_stub,
                                           keyparser):
        config_stub.data = {'input': {'timeout': 0}}
        handle_text((Qt.Key_A, 'a'))
        assert keyparser.execute.called
        assert not keyparser._ambiguous_timer.isActive()

    def test_invalid_keychain(self, handle_text, keyparser):
        handle_text((Qt.Key_B, 'b'))
        handle_text((Qt.Key_C, 'c'))
        assert keyparser._keystring == ''

    def test_ambiguous_delayed_exec(self, handle_text, config_stub, qtbot,
                                    keyparser):
        config_stub.data = CONFIG

        # 'a' is an ambiguous result.
        handle_text((Qt.Key_A, 'a'))
        assert not keyparser.execute.called
        assert keyparser._ambiguous_timer.isActive()
        # We wait for the timeout to occur.
        with qtbot.waitSignal(keyparser.keystring_updated):
            pass
        assert keyparser.execute.called


class TestCount:

    """Test execute() with counts."""

    @pytest.fixture(autouse=True)
    def read_keyparser_config(self, fake_keyconfig, keyparser):
        keyparser.read_config('test')

    def test_no_count(self, handle_text, keyparser):
        """Test with no count added."""
        handle_text((Qt.Key_B, 'b'), (Qt.Key_A, 'a'))
        keyparser.execute.assert_called_once_with(
            'ba', keyparser.Type.chain, None)
        assert keyparser._keystring == ''

    def test_count_0(self, handle_text, keyparser):
        handle_text((Qt.Key_0, '0'), (Qt.Key_B, 'b'), (Qt.Key_A, 'a'))
        calls = [mock.call('0', keyparser.Type.chain, None),
                 mock.call('ba', keyparser.Type.chain, None)]
        keyparser.execute.assert_has_calls(calls)
        assert keyparser._keystring == ''

    def test_count_42(self, handle_text, keyparser):
        handle_text((Qt.Key_4, '4'), (Qt.Key_2, '2'), (Qt.Key_B, 'b'),
                    (Qt.Key_A, 'a'))
        keyparser.execute.assert_called_once_with(
            'ba', keyparser.Type.chain, 42)
        assert keyparser._keystring == ''

    def test_count_42_invalid(self, handle_text, keyparser):
        # Invalid call with ccx gets ignored
        handle_text((Qt.Key_4, '4'), (Qt.Key_2, '2'), (Qt.Key_C, 'c'),
                    (Qt.Key_C, 'c'), (Qt.Key_X, 'x'))
        assert not keyparser.execute.called
        assert keyparser._keystring == ''
        # Valid call with ccc gets the correct count
        handle_text((Qt.Key_6, '2'), (Qt.Key_2, '3'), (Qt.Key_C, 'c'),
                    (Qt.Key_C, 'c'), (Qt.Key_C, 'c'))
        keyparser.execute.assert_called_once_with(
            'ccc', keyparser.Type.chain, 23)
        assert keyparser._keystring == ''


def test_clear_keystring(qtbot, keyparser):
    """Test that the keystring is cleared and the signal is emitted."""
    keyparser._keystring = 'test'
    with qtbot.waitSignal(keyparser.keystring_updated):
        keyparser.clear_keystring()
    assert keyparser._keystring == ''
