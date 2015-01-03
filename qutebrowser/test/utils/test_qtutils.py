# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.utils.qtutils."""

import sys
import argparse
import unittest

from qutebrowser.utils import qtutils


class CheckOverflowTests(unittest.TestCase):

    """Test check_overflow.

    Class attributes:
        INT32_MIN: Minimum valid value for a signed int32.
        INT32_MAX: Maximum valid value for a signed int32.
        INT64_MIN: Minimum valid value for a signed int64.
        INT64_MAX: Maximum valid value for a signed int64.
        GOOD_VALUES: A dict of types mapped to a list of good values.
        BAD_VALUES: A dict of types mapped to a list of bad values.
    """

    INT32_MIN = -(2 ** 31)
    INT32_MAX = 2 ** 31 - 1
    INT64_MIN = -(2 ** 63)
    INT64_MAX = 2 ** 63 - 1

    GOOD_VALUES = {
        'int': [-1, 0, 1, 23.42, INT32_MIN, INT32_MAX],
        'int64': [-1, 0, 1, 23.42, INT64_MIN, INT64_MAX],
    }

    BAD_VALUES = {
        'int': [(INT32_MIN - 1, INT32_MIN),
                (INT32_MAX + 1, INT32_MAX),
                (float(INT32_MAX + 1), INT32_MAX)],
        'int64': [(INT64_MIN - 1, INT64_MIN),
                  (INT64_MAX + 1, INT64_MAX),
                  (float(INT64_MAX + 1), INT64_MAX)],
    }

    def test_good_values(self):
        """Test values which are inside bounds."""
        for ctype, vals in self.GOOD_VALUES.items():
            for val in vals:
                with self.subTest(ctype=ctype, val=val):
                    qtutils.check_overflow(val, ctype)

    def test_bad_values_fatal(self):
        """Test values which are outside bounds with fatal=True."""
        for ctype, vals in self.BAD_VALUES.items():
            for (val, _) in vals:
                with self.subTest(ctype=ctype, val=val):
                    with self.assertRaises(OverflowError):
                        qtutils.check_overflow(val, ctype)

    def test_bad_values_nonfatal(self):
        """Test values which are outside bounds with fatal=False."""
        for ctype, vals in self.BAD_VALUES.items():
            for (val, replacement) in vals:
                with self.subTest(ctype=ctype, val=val):
                    newval = qtutils.check_overflow(val, ctype, fatal=False)
                    self.assertEqual(newval, replacement)


class GetQtArgsTests(unittest.TestCase):

    """Tests for get_args."""

    def setUp(self):
        self.parser = argparse.ArgumentParser()

    def _namespace(self, cmdline, flags=None, args=None):
        """Get an argparse namespace object based on arguments given.

        Args:
            cmdline: The given commandline.
            flags: A list of strings (argument names) for flags without an
                   argument.
            args: A list of arguemnt names for flags with an argument.
        """
        if flags is not None:
            for e in flags:
                self.parser.add_argument(e, action='store_true')
        if args is not None:
            for e in args:
                self.parser.add_argument(e, nargs=1)
        return self.parser.parse_args(cmdline)

    def test_no_qt_args(self):
        """Test commandline with no Qt arguments given."""
        ns = self._namespace(['--foo'], flags=['--foo'])
        self.assertEqual(qtutils.get_args(ns), [sys.argv[0]])

    def test_qt_flag(self):
        """Test commandline with a Qt flag."""
        ns = self._namespace(['--foo', '--qt-reverse', '--bar'],
                             flags=['--foo', '--qt-reverse', '--bar'])
        self.assertEqual(qtutils.get_args(ns), [sys.argv[0], '-reverse'])

    def test_qt_arg(self):
        """Test commandline with a Qt argument."""
        ns = self._namespace(['--qt-stylesheet', 'foobar'],
                             args=['--qt-stylesheet'])
        self.assertEqual(qtutils.get_args(ns), [sys.argv[0], '-stylesheet',
                                                'foobar'])

    def test_qt_both(self):
        """Test commandline with a Qt argument and flag."""
        ns = self._namespace(['--qt-stylesheet', 'foobar', '--qt-reverse'],
                             flags=['--qt-reverse'], args=['--qt-stylesheet'])
        qt_args = qtutils.get_args(ns)
        self.assertEqual(qt_args[0], sys.argv[0])
        self.assertIn('-reverse', qt_args)
        self.assertIn('-stylesheet', qt_args)
        self.assertIn('foobar', qt_args)


if __name__ == '__main__':
    unittest.main()
