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

# pylint: disable=protected-access

"""Tests for the NeighborList class."""

import unittest

from qutebrowser.utils import usertypes


class InitTests(unittest.TestCase):

    """Just try to init some neighborlists.

    Attributes:
        nl: The NeighborList we're testing.
    """

    def test_empty(self):
        """Test constructing an empty NeighborList."""
        nl = usertypes.NeighborList()
        self.assertEqual(nl.items, [])

    def test_items(self):
        """Test constructing an NeighborList with items."""
        nl = usertypes.NeighborList([1, 2, 3])
        self.assertEqual(nl.items, [1, 2, 3])

    def test_len(self):
        """Test len() on NeighborList."""
        nl = usertypes.NeighborList([1, 2, 3])
        self.assertEqual(len(nl), 3)

    def test_contains(self):
        """Test 'in' on NeighborList."""
        nl = usertypes.NeighborList([1, 2, 3])
        self.assertIn(2, nl)
        self.assertNotIn(4, nl)


class DefaultTests(unittest.TestCase):

    """Test the default argument.

    Attributes:
        nl: The NeighborList we're testing.
    """

    def test_simple(self):
        """Test default with a numeric argument."""
        nl = usertypes.NeighborList([1, 2, 3], default=2)
        self.assertEqual(nl._idx, 1)

    def test_none(self):
        """Test default 'None'."""
        nl = usertypes.NeighborList([1, 2, None], default=None)
        self.assertEqual(nl._idx, 2)

    def test_unset(self):
        """Test unset default value."""
        nl = usertypes.NeighborList([1, 2, 3])
        self.assertIsNone(nl._idx)


class EmptyTests(unittest.TestCase):

    """Tests with no items.

    Attributes:
        nl: The NeighborList we're testing.
    """

    def setUp(self):
        self.nl = usertypes.NeighborList()

    def test_curitem(self):
        """Test curitem with no item."""
        with self.assertRaises(IndexError):
            self.nl.curitem()

    def test_firstitem(self):
        """Test firstitem with no item."""
        with self.assertRaises(IndexError):
            self.nl.firstitem()

    def test_lastitem(self):
        """Test lastitem with no item."""
        with self.assertRaises(IndexError):
            self.nl.lastitem()

    def test_getitem(self):
        """Test getitem with no item."""
        with self.assertRaises(IndexError):
            self.nl.getitem(1)


class ItemTests(unittest.TestCase):

    """Tests with items.

    Attributes:
        nl: The NeighborList we're testing.
    """

    def setUp(self):
        self.nl = usertypes.NeighborList([1, 2, 3, 4, 5], default=3)

    def test_curitem(self):
        """Test curitem()."""
        self.assertEqual(self.nl._idx, 2)
        self.assertEqual(self.nl.curitem(), 3)
        self.assertEqual(self.nl._idx, 2)

    def test_nextitem(self):
        """Test nextitem()."""
        self.assertEqual(self.nl.nextitem(), 4)
        self.assertEqual(self.nl._idx, 3)
        self.assertEqual(self.nl.nextitem(), 5)
        self.assertEqual(self.nl._idx, 4)

    def test_previtem(self):
        """Test previtem()."""
        self.assertEqual(self.nl.previtem(), 2)
        self.assertEqual(self.nl._idx, 1)
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl._idx, 0)

    def test_firstitem(self):
        """Test firstitem()."""
        self.assertEqual(self.nl.firstitem(), 1)
        self.assertEqual(self.nl._idx, 0)

    def test_lastitem(self):
        """Test lastitem()."""
        self.assertEqual(self.nl.lastitem(), 5)
        self.assertEqual(self.nl._idx, 4)

    def test_reset(self):
        """Test reset()."""
        self.nl.nextitem()
        self.assertEqual(self.nl._idx, 3)
        self.nl.reset()
        self.assertEqual(self.nl._idx, 2)

    def test_getitem(self):
        """Test getitem()."""
        self.assertEqual(self.nl.getitem(2), 5)
        self.assertEqual(self.nl._idx, 4)
        self.nl.reset()
        self.assertEqual(self.nl.getitem(-2), 1)
        self.assertEqual(self.nl._idx, 0)


class OneTests(unittest.TestCase):

    """Tests with a list with only one item.

    Attributes:
        nl: The NeighborList we're testing.
    """

    def setUp(self):
        self.nl = usertypes.NeighborList([1], default=1)

    def test_first_wrap(self):
        """Test out of bounds previtem() with mode=wrap."""
        self.nl._mode = usertypes.NeighborList.Modes.wrap
        self.nl.firstitem()
        self.assertEqual(self.nl._idx, 0)
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl._idx, 0)

    def test_first_block(self):
        """Test out of bounds previtem() with mode=block."""
        self.nl._mode = usertypes.NeighborList.Modes.block
        self.nl.firstitem()
        self.assertEqual(self.nl._idx, 0)
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl._idx, 0)

    def test_first_raise(self):
        """Test out of bounds previtem() with mode=raise."""
        self.nl._mode = usertypes.NeighborList.Modes.exception
        self.nl.firstitem()
        self.assertEqual(self.nl._idx, 0)
        with self.assertRaises(IndexError):
            self.nl.previtem()
        self.assertEqual(self.nl._idx, 0)

    def test_last_wrap(self):
        """Test out of bounds nextitem() with mode=wrap."""
        self.nl._mode = usertypes.NeighborList.Modes.wrap
        self.nl.lastitem()
        self.assertEqual(self.nl._idx, 0)
        self.assertEqual(self.nl.nextitem(), 1)
        self.assertEqual(self.nl._idx, 0)

    def test_last_block(self):
        """Test out of bounds nextitem() with mode=block."""
        self.nl._mode = usertypes.NeighborList.Modes.block
        self.nl.lastitem()
        self.assertEqual(self.nl._idx, 0)
        self.assertEqual(self.nl.nextitem(), 1)
        self.assertEqual(self.nl._idx, 0)

    def test_last_raise(self):
        """Test out of bounds nextitem() with mode=raise."""
        self.nl._mode = usertypes.NeighborList.Modes.exception
        self.nl.lastitem()
        self.assertEqual(self.nl._idx, 0)
        with self.assertRaises(IndexError):
            self.nl.nextitem()
        self.assertEqual(self.nl._idx, 0)


class BlockTests(unittest.TestCase):

    """Tests with mode=block.

    Attributes:
        nl: The NeighborList we're testing.
    """

    def setUp(self):
        self.nl = usertypes.NeighborList(
            [1, 2, 3, 4, 5], default=3,
            mode=usertypes.NeighborList.Modes.block)

    def test_first(self):
        """Test ouf of bounds previtem()."""
        self.nl.firstitem()
        self.assertEqual(self.nl._idx, 0)
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl._idx, 0)

    def test_last(self):
        """Test ouf of bounds nextitem()."""
        self.nl.lastitem()
        self.assertEqual(self.nl._idx, 4)
        self.assertEqual(self.nl.nextitem(), 5)
        self.assertEqual(self.nl._idx, 4)


class WrapTests(unittest.TestCase):

    """Tests with mode=wrap.

    Attributes:
        nl: The NeighborList we're testing.
    """

    def setUp(self):
        self.nl = usertypes.NeighborList(
            [1, 2, 3, 4, 5], default=3, mode=usertypes.NeighborList.Modes.wrap)

    def test_first(self):
        """Test ouf of bounds previtem()."""
        self.nl.firstitem()
        self.assertEqual(self.nl._idx, 0)
        self.assertEqual(self.nl.previtem(), 5)
        self.assertEqual(self.nl._idx, 4)

    def test_last(self):
        """Test ouf of bounds nextitem()."""
        self.nl.lastitem()
        self.assertEqual(self.nl._idx, 4)
        self.assertEqual(self.nl.nextitem(), 1)
        self.assertEqual(self.nl._idx, 0)


class RaiseTests(unittest.TestCase):

    """Tests with mode=exception.

    Attributes:
        nl: The NeighborList we're testing.
    """

    def setUp(self):
        self.nl = usertypes.NeighborList(
            [1, 2, 3, 4, 5], default=3,
            mode=usertypes.NeighborList.Modes.exception)

    def test_first(self):
        """Test ouf of bounds previtem()."""
        self.nl.firstitem()
        self.assertEqual(self.nl._idx, 0)
        with self.assertRaises(IndexError):
            self.nl.previtem()
        self.assertEqual(self.nl._idx, 0)

    def test_last(self):
        """Test ouf of bounds nextitem()."""
        self.nl.lastitem()
        self.assertEqual(self.nl._idx, 4)
        with self.assertRaises(IndexError):
            self.nl.nextitem()
        self.assertEqual(self.nl._idx, 4)


class SnapInTests(unittest.TestCase):

    """Tests for the fuzzyval/_snap_in features.

    Attributes:
        nl: The NeighborList we're testing.
    """

    def setUp(self):
        self.nl = usertypes.NeighborList([20, 9, 1, 5])

    def test_bigger(self):
        """Test fuzzyval with snapping to a bigger value."""
        self.nl.fuzzyval = 7
        self.assertEqual(self.nl.nextitem(), 9)
        self.assertEqual(self.nl._idx, 1)
        self.assertEqual(self.nl.nextitem(), 1)
        self.assertEqual(self.nl._idx, 2)

    def test_smaller(self):
        """Test fuzzyval with snapping to a smaller value."""
        self.nl.fuzzyval = 7
        self.assertEqual(self.nl.previtem(), 5)
        self.assertEqual(self.nl._idx, 3)
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl._idx, 2)

    def test_equal_bigger(self):
        """Test fuzzyval with matching value, snapping to a bigger value."""
        self.nl.fuzzyval = 20
        self.assertEqual(self.nl.nextitem(), 9)
        self.assertEqual(self.nl._idx, 1)

    def test_equal_smaller(self):
        """Test fuzzyval with matching value, snapping to a smaller value."""
        self.nl.fuzzyval = 5
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl._idx, 2)

    def test_too_big_next(self):
        """Test fuzzyval/next with a value bigger than any in the list."""
        self.nl.fuzzyval = 30
        self.assertEqual(self.nl.nextitem(), 20)
        self.assertEqual(self.nl._idx, 0)

    def test_too_big_prev(self):
        """Test fuzzyval/prev with a value bigger than any in the list."""
        self.nl.fuzzyval = 30
        self.assertEqual(self.nl.previtem(), 20)
        self.assertEqual(self.nl._idx, 0)

    def test_too_small_next(self):
        """Test fuzzyval/next with a value smaller than any in the list."""
        self.nl.fuzzyval = 0
        self.assertEqual(self.nl.nextitem(), 1)
        self.assertEqual(self.nl._idx, 2)

    def test_too_small_prev(self):
        """Test fuzzyval/prev with a value smaller than any in the list."""
        self.nl.fuzzyval = 0
        self.assertEqual(self.nl.previtem(), 1)
        self.assertEqual(self.nl._idx, 2)


if __name__ == '__main__':
    unittest.main()
