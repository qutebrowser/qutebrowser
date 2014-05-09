# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# pylint: disable=missing-docstring

"""Tests for signal utils."""

import unittest
from unittest import TestCase
from unittest.mock import Mock

import qutebrowser.utils.signals as sigutils


class FakeSignal:

    """Fake pyqtSignal stub which uses a mock to see if it was called."""

    def __init__(self, name='fake'):
        self.signal = '2{}(int, int)'.format(name)
        self.emit = Mock()


class TestDebug(TestCase):

    """Test signal debug output functions."""

    def setUp(self):
        self.signal = FakeSignal()

    def test_signal_name(self):
        self.assertEqual(sigutils.signal_name(self.signal), 'fake')

    def test_dbg_signal(self):
        self.assertEqual(sigutils.dbg_signal(self.signal, [23, 42]),
                         'fake(23, 42)')


class TestSignalCache(TestCase):

    """SignalCache tests."""

    def setUp(self):
        self.signal1 = FakeSignal('fake1')
        self.signal2 = FakeSignal('fake2')
        self.cache = sigutils.SignalCache()

    def test_replay(self):
        """Test simple replaying."""
        self.cache.add(self.signal1, [1, 2])
        self.cache.add(self.signal2, [3, 4])
        self.cache.replay()
        self.signal1.emit.assert_called_once_with(1, 2)
        self.signal2.emit.assert_called_once_with(3, 4)

    def test_update(self):
        """Test replaying when a signal was updated."""
        self.cache.add(self.signal1, [1, 2])
        self.cache.add(self.signal2, [3, 4])
        self.cache.add(self.signal1, [5, 6])
        self.cache.replay()
        self.signal1.emit.assert_called_once_with(5, 6)
        self.signal2.emit.assert_called_once_with(3, 4)

    def test_clear(self):
        """Test clearing the signal cache."""
        self.cache.add(self.signal1, [1, 2])
        self.cache.add(self.signal2, [3, 4])
        self.cache.clear()
        self.cache.add(self.signal1, [5, 6])
        self.cache.replay()
        self.signal1.emit.assert_called_once_with(5, 6)

    def test_uncached(self):
        """Test that uncached signals actually are uncached."""
        cache = sigutils.SignalCache(uncached=['fake2'])
        cache.add(self.signal1, [1, 2])
        cache.add(self.signal2, [3, 4])
        cache.replay()
        self.signal1.emit.assert_called_once_with(1, 2)
        self.assertFalse(self.signal2.emit.called)


if __name__ == '__main__':
    unittest.main()
