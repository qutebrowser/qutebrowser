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

"""A model that proxies access to one or more completion categories."""

import typing

from PyQt5.QtCore import Qt, QModelIndex, QAbstractItemModel

from qutebrowser.utils import log, qtutils
from qutebrowser.api import cmdutils


class CompletionModel(QAbstractItemModel):

    """A model that proxies access to one or more completion categories.

    Top level indices represent categories.
    Child indices represent rows of those tables.

    Attributes:
        column_widths: The width percentages of the columns used in the
                       completion view.
        _categories: The sub-categories.
    """

    def __init__(self, *, column_widths=(30, 70, 0), parent=None):
        super().__init__(parent)
        self.column_widths = column_widths
        self._categories = [
        ]  # type: typing.MutableSequence[QAbstractItemModel]

    def _cat_from_idx(self, index):
        """Return the category pointed to by the given index.

        Args:
            idx: A QModelIndex
        Returns:
            A category if the index points at one, else None
        """
        # items hold an index to the parent category in their internalPointer
        # categories have an empty internalPointer
        if index.isValid() and not index.internalPointer():
            return self._categories[index.row()]
        return None

    def add_category(self, cat):
        """Add a completion category to the model."""
        self._categories.append(cat)

    def data(self, index, role=Qt.DisplayRole):
        """Return the item data for index.

        Override QAbstractItemModel::data.

        Args:
            index: The QModelIndex to get item flags for.

        Return: The item data, or None on an invalid index.
        """
        if role != Qt.DisplayRole:
            return None
        cat = self._cat_from_idx(index)
        if cat:
            # category header
            if index.column() == 0:
                return self._categories[index.row()].name
            return None
        # item
        cat = self._cat_from_idx(index.parent())
        if not cat:
            return None
        idx = cat.index(index.row(), index.column())
        return cat.data(idx)

    def flags(self, index):
        """Return the item flags for index.

        Override QAbstractItemModel::flags.

        Return: The item flags, or Qt.NoItemFlags on error.
        """
        if not index.isValid():
            return Qt.NoItemFlags
        if index.parent().isValid():
            # item
            return (Qt.ItemIsEnabled | Qt.ItemIsSelectable |
                    Qt.ItemNeverHasChildren)
        else:
            # category
            return Qt.NoItemFlags

    def index(self, row, col, parent=QModelIndex()):
        """Get an index into the model.

        Override QAbstractItemModel::index.

        Return: A QModelIndex.
        """
        if (row < 0 or row >= self.rowCount(parent) or
                col < 0 or col >= self.columnCount(parent)):
            return QModelIndex()
        if parent.isValid():
            if parent.column() != 0:
                return QModelIndex()
            # store a pointer to the parent category in internalPointer
            return self.createIndex(row, col, self._categories[parent.row()])
        return self.createIndex(row, col, None)

    def parent(self, index):
        """Get an index to the parent of the given index.

        Override QAbstractItemModel::parent.

        Args:
            index: The QModelIndex to get the parent index for.
        """
        parent_cat = index.internalPointer()
        if not parent_cat:
            # categories have no parent
            return QModelIndex()
        row = self._categories.index(parent_cat)
        return self.createIndex(row, 0, None)

    def rowCount(self, parent=QModelIndex()):
        """Override QAbstractItemModel::rowCount."""
        if not parent.isValid():
            # top-level
            return len(self._categories)
        cat = self._cat_from_idx(parent)
        if not cat or parent.column() != 0:
            # item or nonzero category column (only first col has children)
            return 0
        else:
            # category
            return cat.rowCount()

    def columnCount(self, parent=QModelIndex()):
        """Override QAbstractItemModel::columnCount."""
        # pylint: disable=unused-argument
        return 3

    def canFetchMore(self, parent):
        """Override to forward the call to the categories."""
        cat = self._cat_from_idx(parent)
        if cat:
            return cat.canFetchMore(QModelIndex())
        return False

    def fetchMore(self, parent):
        """Override to forward the call to the categories."""
        cat = self._cat_from_idx(parent)
        if cat:
            cat.fetchMore(QModelIndex())

    def count(self):
        """Return the count of non-category items."""
        return sum(t.rowCount() for t in self._categories)

    def set_pattern(self, pattern):
        """Set the filter pattern for all categories.

        Args:
            pattern: The filter pattern to set.
        """
        log.completion.debug("Setting completion pattern '{}'".format(pattern))
        # WORKAROUND:
        # layoutChanged is broken in PyQt 5.7.1, so we must use metaObject
        # https://www.riverbankcomputing.com/pipermail/pyqt/2017-January/038483.html
        meta = self.metaObject()
        meta.invokeMethod(self,  # type: ignore[misc, call-overload]
                          "layoutAboutToBeChanged")
        for cat in self._categories:
            cat.set_pattern(pattern)
        meta.invokeMethod(self,  # type: ignore[misc, call-overload]
                          "layoutChanged")

    def first_item(self):
        """Return the index of the first child (non-category) in the model."""
        for row, cat in enumerate(self._categories):
            if cat.rowCount() > 0:
                parent = self.index(row, 0)
                index = self.index(0, 0, parent)
                qtutils.ensure_valid(index)
                return index
        return QModelIndex()

    def last_item(self):
        """Return the index of the last child (non-category) in the model."""
        for row, cat in reversed(list(enumerate(self._categories))):
            childcount = cat.rowCount()
            if childcount > 0:
                parent = self.index(row, 0)
                index = self.index(childcount - 1, 0, parent)
                qtutils.ensure_valid(index)
                return index
        return QModelIndex()

    def columns_to_filter(self, index):
        """Return the column indices the filter pattern applies to.

        Args:
            index: index of the item to check.

        Return: A list of integers.
        """
        cat = self._cat_from_idx(index.parent())
        return cat.columns_to_filter if cat else []

    def delete_cur_item(self, index):
        """Delete the row at the given index."""
        qtutils.ensure_valid(index)
        parent = index.parent()
        cat = self._cat_from_idx(parent)
        assert cat, "CompletionView sent invalid index for deletion"
        if not cat.delete_func:
            raise cmdutils.CommandError("Cannot delete this item.")

        data = [cat.data(cat.index(index.row(), i))
                for i in range(cat.columnCount())]
        cat.delete_func(data)

        self.beginRemoveRows(parent, index.row(), index.row())
        cat.removeRow(index.row(), QModelIndex())
        self.endRemoveRows()
