# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import re

from PyQt5.QtCore import QSortFilterProxyModel, QModelIndex, Qt

from qutebrowser.utils import log, qtutils, debug
from qutebrowser.completion.models import base as completion


class CompletionFilterModel(QSortFilterProxyModel):

    """Subclass of QSortFilterProxyModel with custom sorting/filtering.

    Attributes:
        pattern: The pattern to filter with.
        srcmodel: The current source model.
                   Kept as attribute because calling `sourceModel` takes quite
                   a long time for some reason.
        _sort_order: The order to use for sorting if using dumb_sort.
    """

    def __init__(self, source, parent=None):
        super().__init__(parent)
        super().setSourceModel(source)
        self.srcmodel = source
        self.pattern = ''

        dumb_sort = self.srcmodel.DUMB_SORT
        if dumb_sort is None:
            # pylint: disable=invalid-name
            self.lessThan = self.intelligentLessThan
            self._sort_order = Qt.AscendingOrder
        else:
            self.setSortRole(completion.Role.sort)
            self._sort_order = dumb_sort

    def set_pattern(self, val):
        """Setter for pattern.

        Invalidates the filter and re-sorts the model.

        Args:
            val: The value to set.
        """
        with debug.log_time(log.completion, 'Setting filter pattern'):
            # empty value clears cache (not necessary for correctness, but
            # helps with keeping memory requirements relatively low)
            if not val:
                self.srcmodel.filtered_out_cache = {}
            self.pattern = val
            self.invalidate()
            sortcol = 0
            self.sort(sortcol)

    def count(self):
        """Get the count of non-toplevel items currently visible.

        Note this only iterates one level deep, as we only need root items
        (categories) and children (items) in our model.
        """
        count = 0
        for i in range(self.rowCount()):
            cat = self.index(i, 0)
            qtutils.ensure_valid(cat)
            count += self.rowCount(cat)
        return count

    def first_item(self):
        """Return the first item in the model."""
        for i in range(self.rowCount()):
            cat = self.index(i, 0)
            qtutils.ensure_valid(cat)
            if cat.model().hasChildren(cat):
                index = self.index(0, 0, cat)
                qtutils.ensure_valid(index)
                return index
        return QModelIndex()

    def last_item(self):
        """Return the last item in the model."""
        for i in range(self.rowCount() - 1, -1, -1):
            cat = self.index(i, 0)
            qtutils.ensure_valid(cat)
            if cat.model().hasChildren(cat):
                index = self.index(self.rowCount(cat) - 1, 0, cat)
                qtutils.ensure_valid(index)
                return index
        return QModelIndex()

    def setSourceModel(self, model):
        """Override QSortFilterProxyModel's setSourceModel to clear pattern."""
        log.completion.debug("Setting source model: {}".format(model))
        self.set_pattern('')
        super().setSourceModel(model)
        self.srcmodel = model

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
        if parent == QModelIndex() or not self.pattern:
            return True

        # first check the cache
        if (parent.row(), row) in self.srcmodel.filtered_out_cache and self.pattern.startswith(self.srcmodel.filtered_out_cache[parent.row(), row]):
            log.completion.debug("According to the cache, row {} in {} has been filtered out.".format(row, parent.data()))
            return False

        data_to_filter = []
        for col in self.srcmodel.columns_to_filter:
            idx = self.srcmodel.index(row, col, parent)
            if not idx.isValid():  # pragma: no cover
                # this is a sanity check not hit by any test case
                continue
            data = self.srcmodel.data(idx)
            if data:
                data_to_filter.append(data)

        # Run the filter on all columns to accept partial matches on each
        # column if they match as a whole.
        # See https://github.com/The-Compiler/qutebrowser/issues/1649
        if data_to_filter:
            data = " ".join(data_to_filter).lower()
            # We know from the cache that if we got here, the row contains all
            # previous terms, so we only need to check the last.
            term = self.pattern.split()[-1].lower()
            if term in data:
                return True

        self.srcmodel.filtered_out_cache[parent.row(), row] = self.pattern
        return False

    def intelligentLessThan(self, lindex, rindex):
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

        left_sort = self.srcmodel.data(lindex, role=completion.Role.sort)
        right_sort = self.srcmodel.data(rindex, role=completion.Role.sort)

        if left_sort is not None and right_sort is not None:
            return left_sort < right_sort

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

    def sort(self, column, order=None):
        """Extend sort to respect self._sort_order if no order was given."""
        if order is None:
            order = self._sort_order
        super().sort(column, order)
