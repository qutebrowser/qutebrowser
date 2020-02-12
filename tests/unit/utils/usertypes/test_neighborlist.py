# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for the NeighborList class."""

import pytest

from qutebrowser.utils import usertypes


class TestInit:

    """Just try to init some neighborlists."""

    def test_empty(self):
        """Test constructing an empty NeighborList."""
        nl = usertypes.NeighborList()
        assert nl.items == []

    def test_items(self):
        """Test constructing a NeighborList with items."""
        nl = usertypes.NeighborList([1, 2, 3])
        assert nl.items == [1, 2, 3]

    def test_len(self):
        """Test len() on NeighborList."""
        nl = usertypes.NeighborList([1, 2, 3])
        assert len(nl) == 3

    def test_contains(self):
        """Test 'in' on NeighborList."""
        nl = usertypes.NeighborList([1, 2, 3])
        assert 2 in nl
        assert 4 not in nl

    def test_invalid_mode(self):
        """Test with an invalid mode."""
        with pytest.raises(TypeError):
            usertypes.NeighborList(mode='blah')


class TestDefaultArg:

    """Test the default argument."""

    def test_simple(self):
        """Test default with a numeric argument."""
        nl = usertypes.NeighborList([1, 2, 3], default=2)
        assert nl._idx == 1

    def test_none(self):
        """Test default 'None'."""
        nl = usertypes.NeighborList([1, 2, None], default=None)
        assert nl._idx == 2

    def test_unset(self):
        """Test unset default value."""
        nl = usertypes.NeighborList([1, 2, 3])
        assert nl._idx is None

    def test_invalid_reset(self):
        """Test reset without default."""
        nl = usertypes.NeighborList([1, 2, 3, 4, 5])
        with pytest.raises(ValueError):
            nl.reset()


class TestEmpty:

    """Tests with no items."""

    @pytest.fixture
    def neighborlist(self):
        return usertypes.NeighborList()

    def test_curitem(self, neighborlist):
        """Test curitem with no item."""
        with pytest.raises(IndexError):
            neighborlist.curitem()

    def test_firstitem(self, neighborlist):
        """Test firstitem with no item."""
        with pytest.raises(IndexError):
            neighborlist.firstitem()

    def test_lastitem(self, neighborlist):
        """Test lastitem with no item."""
        with pytest.raises(IndexError):
            neighborlist.lastitem()

    def test_getitem(self, neighborlist):
        """Test getitem with no item."""
        with pytest.raises(IndexError):
            neighborlist.getitem(1)


class TestItems:

    """Tests with items."""

    @pytest.fixture
    def neighborlist(self):
        return usertypes.NeighborList([1, 2, 3, 4, 5], default=3)

    def test_curitem(self, neighborlist):
        """Test curitem()."""
        assert neighborlist._idx == 2
        assert neighborlist.curitem() == 3
        assert neighborlist._idx == 2

    def test_nextitem(self, neighborlist):
        """Test nextitem()."""
        assert neighborlist.nextitem() == 4
        assert neighborlist._idx == 3
        assert neighborlist.nextitem() == 5
        assert neighborlist._idx == 4

    def test_previtem(self, neighborlist):
        """Test previtem()."""
        assert neighborlist.previtem() == 2
        assert neighborlist._idx == 1
        assert neighborlist.previtem() == 1
        assert neighborlist._idx == 0

    def test_firstitem(self, neighborlist):
        """Test firstitem()."""
        assert neighborlist.firstitem() == 1
        assert neighborlist._idx == 0

    def test_lastitem(self, neighborlist):
        """Test lastitem()."""
        assert neighborlist.lastitem() == 5
        assert neighborlist._idx == 4

    def test_reset(self, neighborlist):
        """Test reset()."""
        neighborlist.nextitem()
        assert neighborlist._idx == 3
        neighborlist.reset()
        assert neighborlist._idx == 2

    def test_getitem(self, neighborlist):
        """Test getitem()."""
        assert neighborlist.getitem(2) == 5
        assert neighborlist._idx == 4
        neighborlist.reset()
        assert neighborlist.getitem(-2) == 1
        assert neighborlist._idx == 0


class TestSingleItem:

    """Tests with a list with only one item."""

    @pytest.fixture
    def neighborlist(self):
        return usertypes.NeighborList([1], default=1)

    def test_first_edge(self, neighborlist):
        """Test out of bounds previtem() with mode=edge."""
        neighborlist._mode = usertypes.NeighborList.Modes.edge
        neighborlist.firstitem()
        assert neighborlist._idx == 0
        assert neighborlist.previtem() == 1
        assert neighborlist._idx == 0

    def test_first_raise(self, neighborlist):
        """Test out of bounds previtem() with mode=raise."""
        neighborlist._mode = usertypes.NeighborList.Modes.exception
        neighborlist.firstitem()
        assert neighborlist._idx == 0
        with pytest.raises(IndexError):
            neighborlist.previtem()
        assert neighborlist._idx == 0

    def test_last_edge(self, neighborlist):
        """Test out of bounds nextitem() with mode=edge."""
        neighborlist._mode = usertypes.NeighborList.Modes.edge
        neighborlist.lastitem()
        assert neighborlist._idx == 0
        assert neighborlist.nextitem() == 1
        assert neighborlist._idx == 0

    def test_last_raise(self, neighborlist):
        """Test out of bounds nextitem() with mode=raise."""
        neighborlist._mode = usertypes.NeighborList.Modes.exception
        neighborlist.lastitem()
        assert neighborlist._idx == 0
        with pytest.raises(IndexError):
            neighborlist.nextitem()
        assert neighborlist._idx == 0


class TestEdgeMode:

    """Tests with mode=edge."""

    @pytest.fixture
    def neighborlist(self):
        return usertypes.NeighborList(
            [1, 2, 3, 4, 5], default=3,
            mode=usertypes.NeighborList.Modes.edge)

    def test_first(self, neighborlist):
        """Test out of bounds previtem()."""
        neighborlist.firstitem()
        assert neighborlist._idx == 0
        assert neighborlist.previtem() == 1
        assert neighborlist._idx == 0

    def test_last(self, neighborlist):
        """Test out of bounds nextitem()."""
        neighborlist.lastitem()
        assert neighborlist._idx == 4
        assert neighborlist.nextitem() == 5
        assert neighborlist._idx == 4


class TestExceptionMode:

    """Tests with mode=exception."""

    @pytest.fixture
    def neighborlist(self):
        return usertypes.NeighborList(
            [1, 2, 3, 4, 5], default=3,
            mode=usertypes.NeighborList.Modes.exception)

    def test_first(self, neighborlist):
        """Test out of bounds previtem()."""
        neighborlist.firstitem()
        assert neighborlist._idx == 0
        with pytest.raises(IndexError):
            neighborlist.previtem()
        assert neighborlist._idx == 0

    def test_last(self, neighborlist):
        """Test out of bounds nextitem()."""
        neighborlist.lastitem()
        assert neighborlist._idx == 4
        with pytest.raises(IndexError):
            neighborlist.nextitem()
        assert neighborlist._idx == 4


class TestSnapIn:

    """Tests for the fuzzyval/_snap_in features."""

    @pytest.fixture
    def neighborlist(self):
        return usertypes.NeighborList([20, 9, 1, 5])

    def test_bigger(self, neighborlist):
        """Test fuzzyval with snapping to a bigger value."""
        neighborlist.fuzzyval = 7
        assert neighborlist.nextitem() == 9
        assert neighborlist._idx == 1
        assert neighborlist.nextitem() == 1
        assert neighborlist._idx == 2

    def test_smaller(self, neighborlist):
        """Test fuzzyval with snapping to a smaller value."""
        neighborlist.fuzzyval = 7
        assert neighborlist.previtem() == 5
        assert neighborlist._idx == 3
        assert neighborlist.previtem() == 1
        assert neighborlist._idx == 2

    def test_equal_bigger(self, neighborlist):
        """Test fuzzyval with matching value, snapping to a bigger value."""
        neighborlist.fuzzyval = 20
        assert neighborlist.nextitem() == 9
        assert neighborlist._idx == 1

    def test_equal_smaller(self, neighborlist):
        """Test fuzzyval with matching value, snapping to a smaller value."""
        neighborlist.fuzzyval = 5
        assert neighborlist.previtem() == 1
        assert neighborlist._idx == 2

    def test_too_big_next(self, neighborlist):
        """Test fuzzyval/next with a value bigger than any in the list."""
        neighborlist.fuzzyval = 30
        assert neighborlist.nextitem() == 20
        assert neighborlist._idx == 0

    def test_too_big_prev(self, neighborlist):
        """Test fuzzyval/prev with a value bigger than any in the list."""
        neighborlist.fuzzyval = 30
        assert neighborlist.previtem() == 20
        assert neighborlist._idx == 0

    def test_too_small_next(self, neighborlist):
        """Test fuzzyval/next with a value smaller than any in the list."""
        neighborlist.fuzzyval = 0
        assert neighborlist.nextitem() == 1
        assert neighborlist._idx == 2

    def test_too_small_prev(self, neighborlist):
        """Test fuzzyval/prev with a value smaller than any in the list."""
        neighborlist.fuzzyval = 0
        assert neighborlist.previtem() == 1
        assert neighborlist._idx == 2
