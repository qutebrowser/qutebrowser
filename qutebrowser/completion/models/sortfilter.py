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

"""A filtering/sorting base model for completions.

Contains:
    CompletionFilterModel -- A QSortFilterProxyModel subclass for completions.
"""

from PyQt5.QtCore import QSortFilterProxyModel, QModelIndex, Qt

from qutebrowser.utils import log, qtutils, debug
from qutebrowser.completion.models import base as completion
from qutebrowser.config import config
import re


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

        If the current completion model overrides sort(), it is used.
        If not, the default implementation in QCompletionFilterModel is called.

        Args:
            val: The value to set.
        """
        with debug.log_time(log.completion, 'Setting filter pattern'):
            self.pattern = val
            self.invalidateFilter()
            sortcol = 0
            try:
                self.srcmodel.sort(sortcol)
            except NotImplementedError:
                self.sort(sortcol)
            self.invalidate()

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

        try:
            return self.srcmodel.custom_filter(self.pattern, row, parent)
        except NotImplementedError:
            for col in self.srcmodel.columns_to_filter:
                idx = self.srcmodel.index(row, col, parent)
                if not idx.isValid():
                    # No entries in parent model
                    continue
                data = self.srcmodel.data(idx)
                if not data:
                    continue
                else:
                    match_functions = {
                        'contain': self._match_contain,
                        'fuzzy': self._match_fuzzy,
                        'start': self._match_start
                    }
                    match_type = config.get('completion', 'match-type')
                    match_function = match_functions[match_type]
                    if match_function(data):
                        return True
            return False

    def _match_fuzzy(self, data):
        """Matcher for 'fuzzy' matching type logic."""
        data = data.casefold()
        pattern = re.escape(self.pattern.casefold())
        last_index = 0
        for char in pattern:
            if char not in data:
                return False
            positions = [g.start() for g in re.finditer(char, data)]
            if max(positions) < last_index:
                return False
            last_index = min(positions)
        return True

    def _match_contain(self, data):
        """Matcher for 'contain' matching type logic."""
        data = data.casefold()
        pattern = self.pattern.casefold()
        return pattern in data

    def _match_start(self, data):
        """Matcher for 'start' matching type logic."""
        protocol = re.compile('^(ht|f)tp(s?)://')
        data = data.casefold()
        pattern = self.pattern.casefold()
        if protocol.match(data) is not None:
            data = protocol.sub('', data)
        return data.startswith(pattern)

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
