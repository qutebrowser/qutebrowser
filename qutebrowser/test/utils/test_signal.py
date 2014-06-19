# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et

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

import qutebrowser.utils.signals as sigutils


class FakeSignal:

    """Fake pyqtSignal stub which uses a mock to see if it was called."""

    def __init__(self, name='fake'):
        self.signal = '2{}(int, int)'.format(name)


class TestDebug(TestCase):

    """Test signal debug output functions."""

    def setUp(self):
        self.signal = FakeSignal()

    def test_signal_name(self):
        self.assertEqual(sigutils.signal_name(self.signal), 'fake')

    def test_dbg_signal(self):
        self.assertEqual(sigutils.dbg_signal(self.signal, [23, 42]),
                         'fake(23, 42)')

    def test_dbg_signal_eliding(self):
        self.assertEqual(sigutils.dbg_signal(self.signal,
                                             [12345678901234567890123]),
                         'fake(1234567890123456789\u2026)')

    def test_dbg_signal_newline(self):
        self.assertEqual(sigutils.dbg_signal(self.signal, ['foo\nbar']),
                         'fake(foo bar)')


if __name__ == '__main__':
    unittest.main()
