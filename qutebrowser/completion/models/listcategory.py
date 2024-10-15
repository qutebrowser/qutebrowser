# SPDX-FileCopyrightText: Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Completion category that uses a list of tuples as a data source."""

import re
from collections.abc import Iterable

from qutebrowser.qt.core import QSortFilterProxyModel, QRegularExpression
from qutebrowser.qt.gui import QStandardItem, QStandardItemModel
from qutebrowser.qt.widgets import QWidget

from qutebrowser.completion.models import util, BaseCategory
from qutebrowser.utils import qtutils, log


class ListCategory(QSortFilterProxyModel, BaseCategory):

    """Expose a list of items as a category for the CompletionModel."""

    def __init__(self,
                 name: str,
                 items: Iterable[tuple[str, ...]],
                 sort: bool = True,
                 delete_func: util.DeleteFuncType = None,
                 parent: QWidget = None):
        super().__init__(parent)
        self.name = name
        self.srcmodel = QStandardItemModel(parent=self)
        self._pattern = ''
        # ListCategory filters all columns
        self.columns_to_filter = [0, 1, 2]
        self.setFilterKeyColumn(-1)
        for item in items:
            self.srcmodel.appendRow([QStandardItem(x) for x in item])
        self.setSourceModel(self.srcmodel)
        self.delete_func = delete_func
        self._sort = sort

    def set_pattern(self, val):
        """Setter for pattern.

        Args:
            val: The value to set.
        """
        if len(val) > 5000:  # avoid crash on huge search terms (#5973)
            log.completion.warning(f"Trimming {len(val)}-char pattern to 5000")
            val = val[:5000]
        self._pattern = val

        # Positive lookahead per search term. This means that all search terms must
        # be matched but they can be matched anywhere in the string, so they can be
        # in any order. For example "foo bar" -> "(?=.*foo)(?=.*bar)"
        re_pattern = "^" + "".join(f"(?=.*{re.escape(term)})" for term in val.split())

        rx = QRegularExpression(re_pattern, QRegularExpression.PatternOption.CaseInsensitiveOption)
        qtutils.ensure_valid(rx)
        self.setFilterRegularExpression(rx)
        self.invalidate()
        sortcol = 0
        self.sort(sortcol)

    def lessThan(self, lindex, rindex):
        """Custom sorting implementation.

        Prefers all items which start with self._pattern. Other than that, uses
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

        if left is None or right is None:  # pragma: no cover
            log.completion.warning("Got unexpected None value, "
                                   "left={!r} right={!r} "
                                   "lindex={!r} rindex={!r}"
                                   .format(left, right, lindex, rindex))
            return False

        leftstart = left.startswith(self._pattern)
        rightstart = right.startswith(self._pattern)

        if leftstart and not rightstart:
            return True
        elif rightstart and not leftstart:
            return False
        elif self._sort:
            return left < right
        else:
            return False
