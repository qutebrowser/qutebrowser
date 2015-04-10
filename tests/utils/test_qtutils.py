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

import pytest

from qutebrowser import qutebrowser
from qutebrowser.utils import qtutils


class OverflowTestCases:
    """
    Provides test data for overflow checking.

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

    @classmethod
    def iter_good_values(cls):
        """
        Yields pairs of (c data type, value) which should pass overflow
        checking.
        """
        for ctype, values in cls.GOOD_VALUES.items():
            for value in values:
                yield ctype, value

    @classmethod
    def iter_bad_values(cls):
        """
        Yields pairs of (c type, value, repl) for values which don't pass
        overflow checking, and value they should be replaced with if overflow
        checking should not be fatal.
        """
        for ctype, values in cls.BAD_VALUES.items():
            for value, repl in values:
                yield ctype, value, repl


class TestCheckOverflow:
    """Test check_overflow.
    """

    @pytest.mark.parametrize('ctype, val', OverflowTestCases.iter_good_values())
    def test_good_values(self, ctype, val):
        """Test values which are inside bounds."""
        qtutils.check_overflow(val, ctype)

    @pytest.mark.parametrize('ctype, val',
                             [(ctype, val) for (ctype, val, _) in
                              OverflowTestCases.iter_bad_values()])
    def test_bad_values_fatal(self, ctype, val):
        """Test values which are outside bounds with fatal=True."""
        with pytest.raises(OverflowError):
            qtutils.check_overflow(val, ctype)

    @pytest.mark.parametrize('ctype, val, repl',
                             OverflowTestCases.iter_bad_values())
    def test_bad_values_nonfatal(self, ctype, val, repl):
        """Test values which are outside bounds with fatal=False."""
        newval = qtutils.check_overflow(val, ctype, fatal=False)
        assert newval == repl


class TestGetQtArgs:
    """Tests for get_args."""

    @pytest.fixture
    def parser(self, mocker):
        """Fixture to provide an argparser.

        Monkey-patches .exit() of the argparser so it doesn't exit on errors.
        """
        parser = qutebrowser.get_argparser()
        mocker.patch.object(parser, 'exit', side_effect=Exception)
        return parser

    def test_no_qt_args(self, parser):
        """Test commandline with no Qt arguments given."""
        args = parser.parse_args(['--debug'])
        assert qtutils.get_args(args) == [sys.argv[0]]

    def test_qt_flag(self, parser):
        """Test commandline with a Qt flag."""
        args = parser.parse_args(['--debug', '--qt-reverse', '--nocolor'])
        assert qtutils.get_args(args) == [sys.argv[0], '-reverse']

    def test_qt_arg(self, parser):
        """Test commandline with a Qt argument."""
        args = parser.parse_args(['--qt-stylesheet', 'foobar'])
        assert qtutils.get_args(args) == [sys.argv[0], '-stylesheet', 'foobar']

    def test_qt_both(self, parser):
        """Test commandline with a Qt argument and flag."""
        args = parser.parse_args(['--qt-stylesheet', 'foobar', '--qt-reverse'])
        qt_args = qtutils.get_args(args)
        assert qt_args[0] == sys.argv[0]
        assert '-reverse' in qt_args
        assert '-stylesheet' in qt_args
        assert 'foobar' in qt_args
