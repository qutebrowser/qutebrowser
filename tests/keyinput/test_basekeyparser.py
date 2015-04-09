# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
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

# pylint: disable=protected-access

"""Tests for BaseKeyParser."""

import logging
from unittest import mock

from PyQt5.QtCore import Qt
import pytest

from qutebrowser.keyinput import basekeyparser
from qutebrowser.utils import objreg, log


CONFIG = {'input': {'timeout': 100}}


BINDINGS = {'test': {'<Ctrl-a>': 'ctrla',
                     'a': 'a',
                     'ba': 'ba',
                     'ax': 'ax',
                     'ccc': 'ccc'},
            'test2': {'foo': 'bar', '<Ctrl+X>': 'ctrlx'}}


@pytest.yield_fixture
def fake_keyconfig():
    """Create a mock of a KeyConfiguration and register it into objreg."""
    fake_keyconfig = mock.Mock(spec=['get_bindings_for'])
    fake_keyconfig.get_bindings_for.side_effect = lambda s: BINDINGS[s]
    objreg.register('key-config', fake_keyconfig)
    yield
    objreg.delete('key-config')


@pytest.fixture
def mock_timer(mocker, stubs):
    """Mock the Timer class used by the usertypes module with a stub."""
    mocker.patch('qutebrowser.keyinput.basekeyparser.usertypes.Timer',
                 new=stubs.FakeTimer)


class TestSplitCount:

    """Test the _split_count method.

    Class Attributes:
        TESTS: list of parameters for the tests, as tuples of
        (input_key, supports_count, expected)
    """

    TESTS = [
        # (input_key, supports_count, expected)
        ('10', True, (10, '')),
        ('10foo', True, (10, 'foo')),
        ('-1foo', True, (None, '-1foo')),
        ('10e4foo', True, (10, 'e4foo')),
        ('foo', True, (None, 'foo')),
        ('10foo', False, (None, '10foo')),
    ]

    @pytest.mark.parametrize('input_key, supports_count, expected', TESTS)
    def test_splitcount(self, input_key, supports_count, expected):
        """Test split_count with only a count."""
        kp = basekeyparser.BaseKeyParser(0, supports_count=supports_count)
        kp._keystring = input_key
        assert kp._split_count() == expected


@pytest.mark.usefixtures('fake_keyconfig', 'mock_timer')
class TestReadConfig:

    """Test reading the config."""

    def test_read_config_invalid(self):
        """Test reading config without setting it before."""
        kp = basekeyparser.BaseKeyParser(0)
        with pytest.raises(ValueError):
            kp.read_config()

    def test_read_config_valid(self):
        """Test reading config."""
        kp = basekeyparser.BaseKeyParser(0, supports_count=True,
                                         supports_chains=True)
        kp.read_config('test')
        assert 'ccc' in kp.bindings
        assert 'ctrl+a' in kp.special_bindings
        kp.read_config('test2')
        assert 'ccc' not in kp.bindings
        assert 'ctrl+a' not in kp.special_bindings
        assert 'foo' in kp.bindings
        assert 'ctrl+x' in kp.special_bindings


@pytest.mark.usefixtures('mock_timer')
class TestSpecialKeys:

    """Check execute() with special keys.

    Attributes:
        kp: The BaseKeyParser to be tested.
    """

    @pytest.fixture(autouse=True)
    def setup(self, caplog, fake_keyconfig):
        self.kp = basekeyparser.BaseKeyParser(0)
        self.kp.execute = mock.Mock()
        with caplog.atLevel(logging.WARNING, log.keyboard.name):
            # Ignoring keychain 'ccc' in mode 'test' because keychains are not
            # supported there.
            self.kp.read_config('test')

    def test_valid_key(self, fake_keyevent_factory):
        """Test a valid special keyevent."""
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, Qt.ControlModifier))
        self.kp.handle(fake_keyevent_factory(Qt.Key_X, Qt.ControlModifier))
        self.kp.execute.assert_called_once_with('ctrla', self.kp.Type.special)

    def test_invalid_key(self, fake_keyevent_factory):
        """Test an invalid special keyevent."""
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, (Qt.ControlModifier |
                                                        Qt.AltModifier)))
        assert not self.kp.execute.called

    def test_keychain(self, fake_keyevent_factory):
        """Test a keychain."""
        self.kp.handle(fake_keyevent_factory(Qt.Key_B))
        self.kp.handle(fake_keyevent_factory(Qt.Key_A))
        assert not self.kp.execute.called


@pytest.mark.usefixtures('mock_timer')
class TestKeyChain:

    """Test execute() with keychain support.

    Attributes:
        kp: The BaseKeyParser to be tested.
    """

    @pytest.fixture(autouse=True)
    def setup(self, fake_keyconfig):
        """Set up mocks and read the test config."""
        self.kp = basekeyparser.BaseKeyParser(0, supports_chains=True,
                                              supports_count=False)
        self.kp.execute = mock.Mock()
        self.kp.read_config('test')

    def test_valid_special_key(self, fake_keyevent_factory):
        """Test valid special key."""
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, Qt.ControlModifier))
        self.kp.handle(fake_keyevent_factory(Qt.Key_X, Qt.ControlModifier))
        self.kp.execute.assert_called_once_with('ctrla', self.kp.Type.special)
        assert self.kp._keystring == ''

    def test_invalid_special_key(self, fake_keyevent_factory):
        """Test invalid special key."""
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, (Qt.ControlModifier |
                                                        Qt.AltModifier)))
        assert not self.kp.execute.called
        assert self.kp._keystring == ''

    def test_keychain(self, fake_keyevent_factory):
        """Test valid keychain."""
        # Press 'x' which is ignored because of no match
        self.kp.handle(fake_keyevent_factory(Qt.Key_X, text='x'))
        # Then start the real chain
        self.kp.handle(fake_keyevent_factory(Qt.Key_B, text='b'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, text='a'))
        self.kp.execute.assert_called_once_with('ba', self.kp.Type.chain, None)
        assert self.kp._keystring == ''

    def test_ambiguous_keychain(self, fake_keyevent_factory, mocker, stubs):
        """Test ambiguous keychain."""
        mocker.patch('qutebrowser.keyinput.basekeyparser.config',
                     new=stubs.ConfigStub(CONFIG))
        timer = self.kp._ambiguous_timer
        assert not timer.isActive()
        # We start with 'a' where the keychain gives us an ambiguous result.
        # Then we check if the timer has been set up correctly
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, text='a'))
        assert not self.kp.execute.called
        assert timer.isSingleShot()
        assert timer.interval() == 100
        assert timer.isActive()
        # Now we type an 'x' and check 'ax' has been executed and the timer
        # stopped.
        self.kp.handle(fake_keyevent_factory(Qt.Key_X, text='x'))
        self.kp.execute.assert_called_once_with('ax', self.kp.Type.chain, None)
        assert not timer.isActive()
        assert self.kp._keystring == ''

    def test_invalid_keychain(self, fake_keyevent_factory):
        """Test invalid keychain."""
        self.kp.handle(fake_keyevent_factory(Qt.Key_B, text='b'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_C, text='c'))
        assert self.kp._keystring == ''


@pytest.mark.usefixtures('mock_timer')
class TestCount:

    """Test execute() with counts."""

    @pytest.fixture(autouse=True)
    def setup(self, fake_keyconfig):
        self.kp = basekeyparser.BaseKeyParser(0, supports_chains=True,
                                              supports_count=True)
        self.kp.execute = mock.Mock()
        self.kp.read_config('test')

    def test_no_count(self, fake_keyevent_factory):
        """Test with no count added."""
        self.kp.handle(fake_keyevent_factory(Qt.Key_B, text='b'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, text='a'))
        self.kp.execute.assert_called_once_with('ba', self.kp.Type.chain, None)
        assert self.kp._keystring == ''

    def test_count_0(self, fake_keyevent_factory):
        """Test with count=0."""
        self.kp.handle(fake_keyevent_factory(Qt.Key_0, text='0'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_B, text='b'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, text='a'))
        self.kp.execute.assert_called_once_with('ba', self.kp.Type.chain, 0)
        assert self.kp._keystring == ''

    def test_count_42(self, fake_keyevent_factory):
        """Test with count=42."""
        self.kp.handle(fake_keyevent_factory(Qt.Key_4, text='4'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_2, text='2'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_B, text='b'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, text='a'))
        self.kp.execute.assert_called_once_with('ba', self.kp.Type.chain, 42)
        assert self.kp._keystring == ''

    def test_count_42_invalid(self, fake_keyevent_factory):
        """Test with count=42 and invalid command."""
        # Invalid call with ccx gets ignored
        self.kp.handle(fake_keyevent_factory(Qt.Key_4, text='4'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_2, text='2'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_B, text='c'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, text='c'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, text='x'))
        assert not self.kp.execute.called
        assert self.kp._keystring == ''
        # Valid call with ccc gets the correct count
        self.kp.handle(fake_keyevent_factory(Qt.Key_4, text='2'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_2, text='3'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_B, text='c'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, text='c'))
        self.kp.handle(fake_keyevent_factory(Qt.Key_A, text='c'))
        self.kp.execute.assert_called_once_with('ccc', self.kp.Type.chain, 23)
        assert self.kp._keystring == ''
