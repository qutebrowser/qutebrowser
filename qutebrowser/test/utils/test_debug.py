# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Tests for qutebrowser.utils.debug."""

import re
import time
import unittest
import logging

from PyQt5.QtCore import Qt

from qutebrowser.utils import debug
from qutebrowser.test import stubs


class QFlagsKeyTests(unittest.TestCase):

    """Tests for qflags_key()."""

    # https://github.com/The-Compiler/qutebrowser/issues/42

    @unittest.skip('FIXME')
    def test_single(self):
        """Test with single value."""
        flags = debug.qflags_key(Qt, Qt.AlignTop)
        self.assertEqual(flags, 'AlignTop')

    @unittest.skip('FIXME')
    def test_multiple(self):
        """Test with multiple values."""
        flags = debug.qflags_key(Qt, Qt.AlignLeft | Qt.AlignTop)
        self.assertEqual(flags, 'AlignLeft|AlignTop')

    def test_combined(self):
        """Test with a combined value."""
        flags = debug.qflags_key(Qt, Qt.AlignCenter)
        self.assertEqual(flags, 'AlignHCenter|AlignVCenter')

    @unittest.skip('FIXME')
    def test_add_base(self):
        """Test with add_base=True."""
        flags = debug.qflags_key(Qt, Qt.AlignTop, add_base=True)
        self.assertEqual(flags, 'Qt.AlignTop')

    def test_int_noklass(self):
        """Test passing an int without explicit klass given."""
        with self.assertRaises(TypeError):
            debug.qflags_key(Qt, 42)

    @unittest.skip('FIXME')
    def test_int(self):
        """Test passing an int with explicit klass given."""
        flags = debug.qflags_key(Qt, 0x0021, klass=Qt.Alignment)
        self.assertEqual(flags, 'AlignLeft|AlignTop')

    def test_unknown(self):
        """Test passing an unknown value."""
        flags = debug.qflags_key(Qt, 0x1100, klass=Qt.Alignment)
        self.assertEqual(flags, '0x0100|0x1000')


class TestDebug(unittest.TestCase):

    """Test signal debug output functions."""

    def setUp(self):
        self.signal = stubs.FakeSignal()

    def test_signal_name(self):
        """Test signal_name()."""
        self.assertEqual(debug.signal_name(self.signal), 'fake')

    def test_dbg_signal(self):
        """Test dbg_signal()."""
        self.assertEqual(debug.dbg_signal(self.signal, [23, 42]),
                         'fake(23, 42)')

    def test_dbg_signal_eliding(self):
        """Test eliding in dbg_signal()."""
        self.assertEqual(debug.dbg_signal(self.signal,
                                          ['x' * 201]),
                         "fake('{}\u2026)".format('x' * 198))

    def test_dbg_signal_newline(self):
        """Test dbg_signal() with a newline."""
        self.assertEqual(debug.dbg_signal(self.signal, ['foo\nbar']),
                         r"fake('foo\nbar')")


class TestLogTime(unittest.TestCase):

    """Test log_time."""

    def test_log_time(self):
        """Test if log_time logs properly."""
        logger = logging.getLogger('qt-tests')
        with self.assertLogs(logger, logging.DEBUG) as logged:
            with debug.log_time(logger, action='foobar'):
                time.sleep(0.1)
            self.assertEqual(len(logged.records), 1)
            pattern = re.compile(r'^Foobar took ([\d.]*) seconds\.$')
            match = pattern.match(logged.records[0].msg)
            self.assertTrue(match)
            duration = float(match.group(1))
            self.assertAlmostEqual(duration, 0.1, delta=0.01)

if __name__ == '__main__':
    unittest.main()
