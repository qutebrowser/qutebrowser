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

"""Custom useful datatypes."""

import logging

# Used as default argument in the constructor so default can be None.
_UNSET = object()


class NeighborList:

    """A list of items which saves it current position.

    Attributes:
        BLOCK/WRAP/RAISE: Modes, see constructor documentation.
        _items: A list of all items, accessed through item property.
        idx: The current position in the list.
        _mode: The current mode.

    """

    BLOCK = 0
    WRAP = 1
    RAISE = 2

    def __init__(self, items=None, default=_UNSET, mode=RAISE):
        """Constructor.

        Args:
            items: The list of items to iterate in.
            _default: The initially selected value.
            _mode: Behaviour when the first/last item is reached.
                   BLOCK: Stay on the selected item
                   WRAP: Wrap around to the other end
                   RAISE: Raise an IndexError.

        """
        if items is None:
            self._items = []
        else:
            self._items = items
        self._default = default
        if default is not _UNSET:
            self.idx = self._items.index(default)
        self._mode = mode

    @property
    def items(self):
        """Getter for items, which should not be set."""
        return self._items

    def getitem(self, offset):
        """Get the item with a relative position.

        Args:
            offset: The offset of the current item, relative to the last one.

        Return:
            The new item.

        Raise:
            IndexError if the border of the list is reached and mode is RAISE.

        """
        # FIXME - zooming somehow wraps...
        logging.debug("{} items, idx {}, offset {}".format(len(self._items),
                                                           self.idx, offset))
        if not self._items:
            raise IndexError("No items found!")
        try:
            if self.idx + offset > 0:
                new = self._items[self.idx + offset]
            else:
                raise IndexError
        except IndexError:
            if self._mode == self.BLOCK:
                new = self.curitem()
            elif self._mode == self.WRAP:
                self.idx += offset
                self.idx %= len(self.items)
                new = self.curitem()
            elif self._mode == self.RAISE:
                raise
        else:
            self.idx += offset
        return new

    def curitem(self):
        """Get the current item in the list."""
        return self._items[self.idx]

    def nextitem(self):
        """Get the next item in the list."""
        return self.getitem(1)

    def previtem(self):
        """Get the previous item in the list."""
        return self.getitem(-1)

    def reset(self):
        """Reset the position to the default."""
        if self._default is _UNSET:
            raise ValueError("No default set!")
        else:
            self.idx = self._items.index(self._default)
            return self.curitem()
