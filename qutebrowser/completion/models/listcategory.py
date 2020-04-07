# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""Completion category that uses a list of tuples as a data source."""

import re
import typing

from PyQt5.QtCore import Qt, QSortFilterProxyModel, QRegExp
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import QWidget

from qutebrowser.completion.models import util
from qutebrowser.utils import qtutils, log


_ItemType = typing.Union[typing.Tuple[str],
                         typing.Tuple[str, str],
                         typing.Tuple[str, str, str]]


class ListCategory(QSortFilterProxyModel):

    """Expose a list of items as a category for the CompletionModel."""

    def __init__(self,
                 name: str,
                 items: typing.Iterable[_ItemType],
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
        self._pattern = val
        val = re.sub(r' +', r' ', val)  # See #1919
        val = re.escape(val)
        val = val.replace(r'\ ', '.*')
        rx = QRegExp(val, Qt.CaseInsensitive)
        self.setFilterRegExp(rx)
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
