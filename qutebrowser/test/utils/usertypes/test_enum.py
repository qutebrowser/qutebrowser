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

"""Tests for the Enum class."""

import unittest
from unittest import TestCase

from qutebrowser.utils.usertypes import enum


class EnumTests(TestCase):

    """Test simple enums."""

    def setUp(self):
        self.enum = enum('zero', 'one')

    def test_values(self):
        self.assertEqual(self.enum.zero, 0)
        self.assertEqual(self.enum.one, 1)

    def test_reverse(self):
        self.assertEqual(self.enum[0], 'zero')
        self.assertEqual(self.enum[1], 'one')

    def test_unknown(self):
        with self.assertRaises(AttributeError):
            _ = self.enum.two

    def test_unknown_reverse(self):
        with self.assertRaises(KeyError):
            _ = self.enum['two']


if __name__ == '__main__':
    unittest.main()
