# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>:
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

import unittest
from unittest import mock

from qutebrowser.keyinput import modeparsers
from qutebrowser.test import stubs, helpers
from qutebrowser.utils import objreg


CONFIG = {'input': {'partial-timeout': 100}}


BINDINGS = {'normal': {'a': 'a', 'ba': 'ba'}}


fake_keyconfig = mock.Mock(spec=['get_bindings_for'])
fake_keyconfig.get_bindings_for.side_effect = lambda s: BINDINGS[s]


@mock.patch('qutebrowser.keyinput.basekeyparser.usertypes.Timer',
            new=stubs.FakeTimer)
@mock.patch('qutebrowser.keyinput.modeparsers.config',
            new=stubs.ConfigStub(CONFIG))
class NormalKeyParserTests(unittest.TestCase):

    """Tests for NormalKeyParser.

    Attributes:
        kp: The NormalKeyParser to be tested.
    """

    # pylint: disable=protected-access

    def setUp(self):
        """Set up mocks and read the test config."""
        objreg.register('key-config', fake_keyconfig)
        self.kp = modeparsers.NormalKeyParser(0)
        self.kp.execute = mock.Mock()

    def tearDown(self):
        objreg.delete('key-config')

    def test_keychain(self):
        """Test valid keychain."""
        # Press 'x' which is ignored because of no match
        self.kp.handle(helpers.fake_keyevent(Qt.Key_X, text='x'))
        # Then start the real chain
        self.kp.handle(helpers.fake_keyevent(Qt.Key_B, text='b'))
        self.kp.handle(helpers.fake_keyevent(Qt.Key_A, text='a'))
        self.kp.execute.assert_called_once_with('ba', self.kp.Type.chain, None)
        self.assertEqual(self.kp._keystring, '')

    def test_partial_keychain_timeout(self):
        """Test partial keychain timeout."""
        timer = self.kp._partial_timer
        self.assertFalse(timer.isActive())
        # Press 'b' for a partial match.
        # Then we check if the timer has been set up correctly
        self.kp.handle(helpers.fake_keyevent(Qt.Key_B, text='b'))
        self.assertTrue(timer.isSingleShot())
        self.assertEqual(timer.interval(), 100)
        self.assertTrue(timer.isActive())

        self.assertFalse(self.kp.execute.called)
        self.assertEqual(self.kp._keystring, 'b')
        # Now simulate a timeout and check the keystring has been cleared.
        keystring_updated_mock = mock.Mock()
        self.kp.keystring_updated.connect(keystring_updated_mock)
        timer.timeout.emit()
        self.assertFalse(self.kp.execute.called)
        self.assertEqual(self.kp._keystring, '')
        keystring_updated_mock.assert_called_once_with('')


if __name__ == '__main__':
    unittest.main()
