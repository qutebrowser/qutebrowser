# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Tests for the Enum class."""

import unittest

from qutebrowser.utils.usertypes import enum


class EnumTests(unittest.TestCase):

    """Test simple enums.

    Attributes:
        enum: The enum we're testing.
    """

    def setUp(self):
        self.enum = enum('zero', 'one')

    def test_values(self):
        """Test if enum members resolve to the right values."""
        self.assertEqual(self.enum.zero, 0)
        self.assertEqual(self.enum.one, 1)

    def test_reverse(self):
        """Test reverse mapping."""
        self.assertEqual(self.enum[0], 'zero')
        self.assertEqual(self.enum[1], 'one')

    def test_unknown(self):
        """Test invalid values which should raise an AttributeError."""
        with self.assertRaises(AttributeError):
            _ = self.enum.two

    def test_unknown_reverse(self):
        """Test reverse mapping with invalid value ."""
        with self.assertRaises(KeyError):
            _ = self.enum['two']

    def test_start(self):
        """Test the start= argument."""
        e = enum('three', 'four', start=3)
        self.assertEqual(e.three, 3)
        self.assertEqual(e.four, 4)


if __name__ == '__main__':
    unittest.main()
