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
import unittest
from unittest import mock

from PyQt5.QtCore import Qt

from qutebrowser.keyinput import basekeyparser
from qutebrowser.test import stubs, helpers
from qutebrowser.utils import objreg


CONFIG = {'input': {'timeout': 100}}


BINDINGS = {'test': {'<Ctrl-a>': 'ctrla',
                     'a': 'a',
                     'ba': 'ba',
                     'ax': 'ax',
                     'ccc': 'ccc'},
            'test2': {'foo': 'bar', '<Ctrl+X>': 'ctrlx'}}


fake_keyconfig = mock.Mock(spec=['get_bindings_for'])
fake_keyconfig.get_bindings_for.side_effect = lambda s: BINDINGS[s]


def setUpModule():
    """Mock out some imports in basekeyparser."""
    basekeyparser.QObject = mock.Mock()
    logging.disable(logging.WARNING)


def tearDownModule():
    """Restore mocked out stuff."""
    logging.disable(logging.NOTSET)


class SplitCountTests(unittest.TestCase):

    """Test the _split_count method.

    Attributes:
        kp: The BaseKeyParser we're testing.
    """

    def setUp(self):
        self.kp = basekeyparser.BaseKeyParser(0, supports_count=True)

    def test_onlycount(self):
        """Test split_count with only a count."""
        self.kp._keystring = '10'
        self.assertEqual(self.kp._split_count(), (10, ''))

    def test_normalcount(self):
        """Test split_count with count and text."""
        self.kp._keystring = '10foo'
        self.assertEqual(self.kp._split_count(), (10, 'foo'))

    def test_minuscount(self):
        """Test split_count with a negative count."""
        self.kp._keystring = '-1foo'
        self.assertEqual(self.kp._split_count(), (None, '-1foo'))

    def test_expcount(self):
        """Test split_count with an exponential count."""
        self.kp._keystring = '10e4foo'
        self.assertEqual(self.kp._split_count(), (10, 'e4foo'))

    def test_nocount(self):
        """Test split_count with only a command."""
        self.kp._keystring = 'foo'
        self.assertEqual(self.kp._split_count(), (None, 'foo'))

    def test_nosupport(self):
        """Test split_count with a count when counts aren't supported."""
        self.kp._supports_count = False
        self.kp._keystring = '10foo'
        self.assertEqual(self.kp._split_count(), (None, '10foo'))


class ReadConfigTests(unittest.TestCase):

    """Test reading the config."""

    def setUp(self):
        objreg.register('key-config', fake_keyconfig)
        basekeyparser.usertypes.Timer = mock.Mock()

    def tearDown(self):
        objreg.delete('key-config')

    def test_read_config_invalid(self):
        """Test reading config without setting it before."""
        kp = basekeyparser.BaseKeyParser(0)
        with self.assertRaises(ValueError):
            kp.read_config()

    def test_read_config_valid(self):
        """Test reading config."""
        kp = basekeyparser.BaseKeyParser(0, supports_count=True,
                                         supports_chains=True)
        kp.read_config('test')
        self.assertIn('ccc', kp.bindings)
        self.assertIn('ctrl+a', kp.special_bindings)
        kp.read_config('test2')
        self.assertNotIn('ccc', kp.bindings)
        self.assertNotIn('ctrl+a', kp.special_bindings)
        self.assertIn('foo', kp.bindings)
        self.assertIn('ctrl+x', kp.special_bindings)


class SpecialKeysTests(unittest.TestCase):

    """Check execute() with special keys.

    Attributes:
        kp: The BaseKeyParser to be tested.
    """

    def setUp(self):
        patcher = mock.patch(
            'qutebrowser.keyinput.basekeyparser.usertypes.Timer',
            autospec=True)
        patcher.start()
        objreg.register('key-config', fake_keyconfig)
        self.addCleanup(patcher.stop)
        self.kp = basekeyparser.BaseKeyParser(0)
        self.kp.execute = mock.Mock()
        self.kp.read_config('test')

    def tearDown(self):
        objreg.delete('key-config')

    def test_valid_key(self):
        """Test a valid special keyevent."""
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, Qt.ControlModifier))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_X, Qt.ControlModifier))
        self.kp.execute.assert_called_once_with('ctrla', self.kp.Type.special)

    def test_invalid_key(self):
        """Test an invalid special keyevent."""
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, (Qt.ControlModifier |
                                                        Qt.AltModifier)))
        self.assertFalse(self.kp.execute.called)

    def test_keychain(self):
        """Test a keychain."""
        self.kp.handle(helpers.fake_keyevent(Qt.Key_B))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A))
        self.assertFalse(self.kp.execute.called)


class KeyChainTests(unittest.TestCase):

    """Test execute() with keychain support.

    Attributes:
        kp: The BaseKeyParser to be tested.
        timermock: The mock to be used as timer.
    """

    def setUp(self):
        """Set up mocks and read the test config."""
        objreg.register('key-config', fake_keyconfig)
        self.timermock = mock.Mock()
        basekeyparser.usertypes.Timer = mock.Mock(return_value=self.timermock)
        self.kp = basekeyparser.BaseKeyParser(0, supports_chains=True,
                                              supports_count=False)
        self.kp.execute = mock.Mock()
        self.kp.read_config('test')

    def tearDown(self):
        objreg.delete('key-config')

    def test_valid_special_key(self):
        """Test valid special key."""
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, Qt.ControlModifier))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_X, Qt.ControlModifier))
        self.kp.execute.assert_called_once_with('ctrla', self.kp.Type.special)
        self.assertEqual(self.kp._keystring, '')

    def test_invalid_special_key(self):
        """Test invalid special key."""
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, (Qt.ControlModifier |
                                                        Qt.AltModifier)))
        self.assertFalse(self.kp.execute.called)
        self.assertEqual(self.kp._keystring, '')

    def test_keychain(self):
        """Test valid keychain."""
        # Press 'x' which is ignored because of no match
        self.kp.handle(helpers.fake_keyevent(Qt.Key_X, text='x'))
        # Then start the real chain
        self.kp.handle(helpers.fake_keyevent(Qt.Key_B, text='b'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, text='a'))
        self.kp.execute.assert_called_once_with('ba', self.kp.Type.chain, None)
        self.assertEqual(self.kp._keystring, '')

    def test_ambigious_keychain(self):
        """Test ambigious keychain."""
        basekeyparser.config = stubs.ConfigStub(CONFIG)
        # We start with 'a' where the keychain gives us an ambigious result.
        # Then we check if the timer has been set up correctly
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, text='a'))
        self.assertFalse(self.kp.execute.called)
        basekeyparser.usertypes.Timer.assert_called_once_with(
            self.kp, 'ambigious_match')
        self.timermock.setSingleShot.assert_called_once_with(True)
        self.timermock.setInterval.assert_called_once_with(100)
        self.assertTrue(self.timermock.timeout.connect.called)
        self.assertFalse(self.timermock.stop.called)
        self.timermock.start.assert_called_once_with()
        # Now we type an 'x' and check 'ax' has been executed and the timer
        # stopped.
        self.kp.handle(helpers.fake_keyevent(Qt.Key_X, text='x'))
        self.kp.execute.assert_called_once_with('ax', self.kp.Type.chain, None)
        self.timermock.stop.assert_called_once_with()
        self.assertEqual(self.kp._keystring, '')

    def test_invalid_keychain(self):
        """Test invalid keychain."""
        self.kp.handle(helpers.fake_keyevent(Qt.Key_B, text='b'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_C, text='c'))
        self.assertEqual(self.kp._keystring, '')


class CountTests(unittest.TestCase):

    """Test execute() with counts."""

    def setUp(self):
        objreg.register('key-config', fake_keyconfig)
        basekeyparser.usertypes.Timer = mock.Mock()
        self.kp = basekeyparser.BaseKeyParser(0, supports_chains=True,
                                              supports_count=True)
        self.kp.execute = mock.Mock()
        self.kp.read_config('test')

    def test_no_count(self):
        """Test with no count added."""
        self.kp.handle(helpers.fake_keyevent(Qt.Key_B, text='b'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, text='a'))
        self.kp.execute.assert_called_once_with('ba', self.kp.Type.chain, None)
        self.assertEqual(self.kp._keystring, '')

    def test_count_0(self):
        """Test with count=0."""
        self.kp.handle(helpers.fake_keyevent(Qt.Key_0, text='0'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_B, text='b'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, text='a'))
        self.kp.execute.assert_called_once_with('ba', self.kp.Type.chain, 0)
        self.assertEqual(self.kp._keystring, '')

    def test_count_42(self):
        """Test with count=42."""
        self.kp.handle(helpers.fake_keyevent(Qt.Key_4, text='4'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_2, text='2'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_B, text='b'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, text='a'))
        self.kp.execute.assert_called_once_with('ba', self.kp.Type.chain, 42)
        self.assertEqual(self.kp._keystring, '')

    def test_count_42_invalid(self):
        """Test with count=42 and invalid command."""
        # Invalid call with ccx gets ignored
        self.kp.handle(helpers.fake_keyevent(Qt.Key_4, text='4'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_2, text='2'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_B, text='c'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, text='c'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, text='x'))
        self.assertFalse(self.kp.execute.called)
        self.assertEqual(self.kp._keystring, '')
        # Valid call with ccc gets the correct count
        self.kp.handle(helpers.fake_keyevent(Qt.Key_4, text='2'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_2, text='3'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_B, text='c'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, text='c'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, text='c'))
        self.kp.execute.assert_called_once_with('ccc', self.kp.Type.chain, 23)
        self.assertEqual(self.kp._keystring, '')

    def tearDown(self):
        objreg.delete('key-config')


if __name__ == '__main__':
    unittest.main()
