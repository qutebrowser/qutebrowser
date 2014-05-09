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

# pylint: disable=protected-access,missing-docstring

"""Tests for the NeighborList class."""

import unittest
from unittest import TestCase

from qutebrowser.utils.usertypes import NeighborList


class InitTests(TestCase):

    """Just try to init some neighborlists."""

    def test_empty(self):
        nl = NeighborList()
        self.assertEqual(nl.items, [])

    def test_items(self):
        nl = NeighborList([1, 2, 3])
        self.assertEqual(nl.items, [1, 2, 3])

    def test_len(self):
        nl = NeighborList([1, 2, 3])
        self.assertEqual(len(nl), 3)

    def test_repr(self):
        nl = NeighborList([1, 2, 3])
        self.assertEqual(repr(nl), 'NeighborList([1, 2, 3])')

    def test_contains(self):
        nl = NeighborList([1, 2, 3])
        self.assertIn(2, nl)
        self.assertNotIn(4, nl)


class DefaultTests(TestCase):

    """Test the default argument."""

    def test_simple(self):
        nl = NeighborList([1, 2, 3], default=2)
        self.assertEqual(nl.idx, 1)

    def test_none(self):
        nl = NeighborList([1, 2, None], default=None)
        self.assertEqual(nl.idx, 2)

    def test_unset(self):
        nl = NeighborList([1, 2, 3])
        self.assertIsNone(nl.idx)


class EmptyTests(TestCase):

    """Tests with no items."""

    def setUp(self):
        self.nl = NeighborList()

    def test_curitem(self):
        with self.assertRaises(IndexError):
            self.nl.curitem()

    def test_firstitem(self):
        with self.assertRaises(IndexError):
            self.nl.firstitem()

    def test_lastitem(self):
        with self.assertRaises(IndexError):
            self.nl.lastitem()

    def test_getitem(self):
        with self.assertRaises(IndexError):
            self.nl.getitem(1)


class ItemTests(TestCase):

    """Tests with items."""

    def setUp(self):
        self.nl = NeighborList([1, 2, 3, 4, 5], default=3)

    def test_curitem(self):
        self.assertEqual(self.nl.idx, 2)
        self.assertEqual(self.nl.curitem(), 3)
        self.assertEqual(self.nl.idx, 2)

    def test_nextitem(self):
        self.assertEqual(self.nl.nextitem(), 4)
        self.assertEqual(self.nl.idx, 3)
        self.assertEqual(self.nl.nextitem(), 5)
        self.assertEqual(self.nl.idx, 4)

    def test_previtem(self):
        self.assertEqual(self.nl.previtem(), 2)
        self.assertEqual(self.nl.idx, 1)
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl.idx, 0)

    def test_firstitem(self):
        self.assertEqual(self.nl.firstitem(), 1)
        self.assertEqual(self.nl.idx, 0)

    def test_lastitem(self):
        self.assertEqual(self.nl.lastitem(), 5)
        self.assertEqual(self.nl.idx, 4)

    def test_reset(self):
        self.nl.nextitem()
        self.assertEqual(self.nl.idx, 3)
        self.nl.reset()
        self.assertEqual(self.nl.idx, 2)

    def test_getitem(self):
        self.assertEqual(self.nl.getitem(2), 5)
        self.assertEqual(self.nl.idx, 4)
        self.nl.reset()
        self.assertEqual(self.nl.getitem(-2), 1)
        self.assertEqual(self.nl.idx, 0)


class OneTests(TestCase):

    """Tests with a list with only one item."""

    def setUp(self):
        self.nl = NeighborList([1], default=1)

    def test_first_wrap(self):
        self.nl._mode = NeighborList.Modes.wrap
        self.nl.firstitem()
        self.assertEqual(self.nl.idx, 0)
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl.idx, 0)

    def test_first_block(self):
        self.nl._mode = NeighborList.Modes.block
        self.nl.firstitem()
        self.assertEqual(self.nl.idx, 0)
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl.idx, 0)

    def test_first_raise(self):
        self.nl._mode = NeighborList.Modes.exception
        self.nl.firstitem()
        self.assertEqual(self.nl.idx, 0)
        with self.assertRaises(IndexError):
            self.nl.previtem()
        self.assertEqual(self.nl.idx, 0)

    def test_last_wrap(self):
        self.nl._mode = NeighborList.Modes.wrap
        self.nl.lastitem()
        self.assertEqual(self.nl.idx, 0)
        self.assertEqual(self.nl.nextitem(), 1)
        self.assertEqual(self.nl.idx, 0)

    def test_last_block(self):
        self.nl._mode = NeighborList.Modes.block
        self.nl.lastitem()
        self.assertEqual(self.nl.idx, 0)
        self.assertEqual(self.nl.nextitem(), 1)
        self.assertEqual(self.nl.idx, 0)

    def test_last_raise(self):
        self.nl._mode = NeighborList.Modes.exception
        self.nl.lastitem()
        self.assertEqual(self.nl.idx, 0)
        with self.assertRaises(IndexError):
            self.nl.nextitem()
        self.assertEqual(self.nl.idx, 0)


class BlockTests(TestCase):

    """Tests with mode=block."""

    def setUp(self):
        self.nl = NeighborList([1, 2, 3, 4, 5], default=3,
                               mode=NeighborList.Modes.block)

    def test_first(self):
        self.nl.firstitem()
        self.assertEqual(self.nl.idx, 0)
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl.idx, 0)

    def test_last(self):
        self.nl.lastitem()
        self.assertEqual(self.nl.idx, 4)
        self.assertEqual(self.nl.nextitem(), 5)
        self.assertEqual(self.nl.idx, 4)


class WrapTests(TestCase):

    """Tests with mode=wrap."""

    def setUp(self):
        self.nl = NeighborList([1, 2, 3, 4, 5], default=3,
                               mode=NeighborList.Modes.wrap)

    def test_first(self):
        self.nl.firstitem()
        self.assertEqual(self.nl.idx, 0)
        self.assertEqual(self.nl.previtem(), 5)
        self.assertEqual(self.nl.idx, 4)

    def test_last(self):
        self.nl.lastitem()
        self.assertEqual(self.nl.idx, 4)
        self.assertEqual(self.nl.nextitem(), 1)
        self.assertEqual(self.nl.idx, 0)


class RaiseTests(TestCase):

    """Tests with mode=exception."""

    def setUp(self):
        self.nl = NeighborList([1, 2, 3, 4, 5], default=3,
                               mode=NeighborList.Modes.exception)

    def test_first(self):
        self.nl.firstitem()
        self.assertEqual(self.nl.idx, 0)
        with self.assertRaises(IndexError):
            self.nl.previtem()
        self.assertEqual(self.nl.idx, 0)

    def test_last(self):
        self.nl.lastitem()
        self.assertEqual(self.nl.idx, 4)
        with self.assertRaises(IndexError):
            self.nl.nextitem()
        self.assertEqual(self.nl.idx, 4)


class SnapInTests(TestCase):

    """Tests for the fuzzyval/_snap_in features."""

    def setUp(self):
        self.nl = NeighborList([20, 9, 1, 5])

    def test_bigger(self):
        self.nl.fuzzyval = 7
        self.assertEqual(self.nl.nextitem(), 9)
        self.assertEqual(self.nl.idx, 1)
        self.assertEqual(self.nl.nextitem(), 1)
        self.assertEqual(self.nl.idx, 2)

    def test_smaller(self):
        self.nl.fuzzyval = 7
        self.assertEqual(self.nl.previtem(), 5)
        self.assertEqual(self.nl.idx, 3)
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl.idx, 2)

    def test_equal_bigger(self):
        self.nl.fuzzyval = 9
        self.assertEqual(self.nl.nextitem(), 9)
        self.assertEqual(self.nl.idx, 1)
        self.assertEqual(self.nl.nextitem(), 1)
        self.assertEqual(self.nl.idx, 2)

    def test_equal_smaller(self):
        self.nl.fuzzyval = 9
        self.assertEqual(self.nl.previtem(), 9)
        self.assertEqual(self.nl.idx, 1)
        self.assertEqual(self.nl.previtem(), 20)
        self.assertEqual(self.nl.idx, 0)


if __name__ == '__main__':
    unittest.main()
