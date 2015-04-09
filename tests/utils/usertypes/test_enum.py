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

"""Tests for the Enum class."""

import unittest

from qutebrowser.utils import usertypes

# FIXME: Add some more tests, e.g. for is_int


class EnumTests(unittest.TestCase):

    """Test simple enums.

    Attributes:
        enum: The enum we're testing.
    """

    def setUp(self):
        self.enum = usertypes.enum('Enum', ['one', 'two'])

    def test_values(self):
        """Test if enum members resolve to the right values."""
        self.assertEqual(self.enum.one.value, 1)
        self.assertEqual(self.enum.two.value, 2)

    def test_name(self):
        """Test .name mapping."""
        self.assertEqual(self.enum.one.name, 'one')
        self.assertEqual(self.enum.two.name, 'two')

    def test_unknown(self):
        """Test invalid values which should raise an AttributeError."""
        with self.assertRaises(AttributeError):
            _ = self.enum.three

    def test_start(self):
        """Test the start= argument."""
        e = usertypes.enum('Enum', ['three', 'four'], start=3)
        self.assertEqual(e.three.value, 3)
        self.assertEqual(e.four.value, 4)


if __name__ == '__main__':
    unittest.main()
