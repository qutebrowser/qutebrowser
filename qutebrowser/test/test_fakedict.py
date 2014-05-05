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

"""Tests for the FakeDict class."""

import unittest
from unittest import TestCase

from qutebrowser.utils.usertypes import FakeDict


class FakeDictTests(TestCase):

    """Test the FakeDict usertype."""

    def setUp(self):
        self.fd = FakeDict("foo")

    def test_getattr(self):
        self.assertEqual(self.fd["eggs"], "foo")
        self.assertEqual(self.fd["bacon"], "foo")

    def test_setattr(self):
        with self.assertRaises(TypeError):
            self.fd["eggs"] = "bar"


if __name__ == '__main__':
    unittest.main()
