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

"""A filtering/sorting base model for completions.

Contains:
    CompletionFilterModel -- A QSortFilterProxyModel subclass for completions.

"""

import logging

from PyQt5.QtCore import QSortFilterProxyModel, QModelIndex


class CompletionFilterModel(QSortFilterProxyModel):

    """Subclass of QSortFilterProxyModel with custom sorting/filtering.

    Attributes:
        _pattern: The pattern to filter with, used in pattern property.

    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pattern = ''

    @property
    def pattern(self):
        """Getter for pattern."""
        return self._pattern

    @pattern.setter
    def pattern(self, val):
        """Setter for pattern.

        Invalidates the filter and re-sorts the model.

        If the current completion model overrides sort(), it is used.
        If not, the default implementation in QCompletionFilterModel is called.

        Args:
            val: The value to set.

        """
        self._pattern = val
        self.invalidateFilter()
        sortcol = 0
        if self.sourceModel() is not None:
            try:
                self.sourceModel().sort(sortcol)
            except NotImplementedError:
                self.sort(sortcol)
            self.invalidate()

    def first_item(self):
        """Return the first item in the model."""
        cat = self.index(0, 0)
        return self.index(0, 0, cat)

    def last_item(self):
        """Return the last item in the model."""
        cat = self.index(self.rowCount() - 1, 0)
        return self.index(self.rowCount(cat) - 1, 0, cat)

    def setSourceModel(self, model):
        """Override QSortFilterProxyModel's setSourceModel to clear pattern."""
        logging.debug("Setting source model: {}".format(model))
        self.pattern = ''
        super().setSourceModel(model)

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
        if parent == QModelIndex():
            return True
        idx = self.sourceModel().index(row, 0, parent)
        data = self.sourceModel().data(idx).value()
        # TODO more sophisticated filtering
        if not self.pattern:
            return True
        return self.pattern in data

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
        left = self.sourceModel().data(lindex).value()
        right = self.sourceModel().data(rindex).value()

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
