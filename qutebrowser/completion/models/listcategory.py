# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""The base completion model for completion in the command line.

Module attributes:
    Role: An enum of user defined model roles.
"""

import re

from PyQt5.QtCore import QSortFilterProxyModel
from PyQt5.QtGui import QStandardItem, QStandardItemModel

from qutebrowser.utils import qtutils, debug, log


class ListCategory(QSortFilterProxyModel):

    """Expose a list of items as a category for the CompletionModel."""

    def __init__(self, name, items, columns_to_filter=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.srcmodel = QStandardItemModel(parent=self)
        self.pattern = ''
        self.pattern_re = None
        self.columns_to_filter = columns_to_filter or [0]
        for item in items:
            self.srcmodel.appendRow([QStandardItem(x) for x in item])
        self.setSourceModel(self.srcmodel)

    def set_pattern(self, val):
        """Setter for pattern.

        Args:
            val: The value to set.
        """
        self.pattern = val
        val = re.sub(r' +', r' ', val)  # See #1919
        val = re.escape(val)
        val = val.replace(r'\ ', '.*')
        self.pattern_re = re.compile(val, re.IGNORECASE)
        self.invalidate()
        sortcol = 0
        self.sort(sortcol)

    def filterAcceptsRow(self, row, parent):
        """Custom filter implementation.

        Override QSortFilterProxyModel::filterAcceptsRow.

        Args:
            row: The row of the item.
            parent: The parent item QModelIndex.

        Return:
            True if self.pattern is contained in item, or if it's a root item
            (category). False in all other cases
        """
        if not self.pattern:
            return True

        for col in self.columns_to_filter:
            idx = self.srcmodel.index(row, col, parent)
            if not idx.isValid():  # pragma: no cover
                # this is a sanity check not hit by any test case
                continue
            data = self.srcmodel.data(idx)
            if not data:
                continue
            elif self.pattern_re.search(data):
                return True
        return False

    def lessThan(self, lindex, rindex):
        """Custom sorting implementation.

        Prefers all items which start with self.pattern. Other than that, uses
        normal Python string sorting.

        Args:
            lindex: The QModelIndex of the left item (*left* < right)
            rindex: The QModelIndex of the right item (left < *right*)

        Return:
            True if left < right, else False
        """
        qtutils.ensure_valid(lindex)
        qtutils.ensure_valid(rindex)

        left = self.srcmodel.data(lindex)
        right = self.srcmodel.data(rindex)

        leftstart = left.startswith(self.pattern)
        rightstart = right.startswith(self.pattern)

        if leftstart and rightstart:
            return left < right
        elif leftstart:
            return True
        elif rightstart:
            return False
        else:
            return left < right
