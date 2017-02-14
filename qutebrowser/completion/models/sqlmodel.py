# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""A completion model backed by SQL tables."""

import re

from PyQt5.QtCore import Qt, QModelIndex, QAbstractItemModel
from PyQt5.QtSql import QSqlQuery, QSqlQueryModel, QSqlDatabase

from qutebrowser.utils import log
from qutebrowser.misc import sql


class SqlCompletionCategory(QSqlQueryModel):
    def __init__(self, name, sort_by, sort_order, limit, columns_to_filter,
                 parent=None):
        super().__init__(parent=parent)
        self.tablename = name

        query = sql.run_query('select * from {} limit 1'.format(name))
        self._fields = [query.record().fieldName(i) for i in columns_to_filter]

        querystr = 'select * from {} where '.format(self.tablename)
        querystr += ' or '.join('{} like ?'.format(f) for f in self._fields)
        querystr += " escape '\\'"

        if sort_by:
            sortstr = 'asc' if sort_order == Qt.AscendingOrder else 'desc'
            querystr += ' order by {} {}'.format(sort_by, sortstr)

        if limit:
            querystr += ' limit {}'.format(limit)

        self._querystr = querystr
        self.set_pattern('%')

    def set_pattern(self, pattern):
        query = sql.run_query(self._querystr, [pattern for _ in self._fields])
        self.setQuery(query)


class SqlCompletionModel(QAbstractItemModel):

    """A sqlite-based model that provides data for the CompletionView.

    This model is a wrapper around one or more sql tables. The tables are all
    stored in a single database in qutebrowser's cache directory.

    Top level indices represent categories, each of which is backed by a single
    table. Child indices represent rows of those tables.

    Class Attributes:
        COLUMN_WIDTHS: The width percentages of the columns used in the
                       completion view.

    Attributes:
        column_widths: The width percentages of the columns used in the
                        completion view.
        columns_to_filter: A list of indices of columns to apply the filter to.
        pattern: Current filter pattern, used for highlighting.
        _categories: The category tables.
    """

    def __init__(self, column_widths=(30, 70, 0), columns_to_filter=None,
                 parent=None):
        super().__init__(parent)
        self.columns_to_filter = columns_to_filter or [0]
        self.column_widths = column_widths
        self._categories = []
        self.srcmodel = self  # TODO: dummy for compat with old API
        self.pattern = ''

    def new_category(self, name, sort_by=None, sort_order=None, limit=None):
        """Create a new completion category and add it to this model.

        Args:
            name: Name of category, and the table in the database.
            sort_by: The name of the field to sort by, or None for no sorting.
            sort_order: Sorting order, if sort_by is non-None.

        Return: A new CompletionCategory.
        """
        cat = SqlCompletionCategory(name, parent=self, sort_by=sort_by,
                                    sort_order=sort_order, limit=limit,
                                    columns_to_filter=self.columns_to_filter)
        self._categories.append(cat)

    def delete_cur_item(self, completion):
        """Delete the selected item."""
        raise NotImplementedError

    def data(self, index, role=Qt.DisplayRole):
        """Return the item data for index.

        Override QAbstractItemModel::data.

        Args:
            index: The QModelIndex to get item flags for.

        Return: The item data, or None on an invalid index.
        """
        if not index.isValid() or role != Qt.DisplayRole:
            return
        if not index.parent().isValid():
            if index.column() == 0:
                return self._categories[index.row()].tablename
        else:
            table = self._categories[index.parent().row()]
            idx = table.index(index.row(), index.column())
            return table.data(idx)

    def flags(self, index):
        """Return the item flags for index.

        Override QAbstractItemModel::flags.

        Return: The item flags, or Qt.NoItemFlags on error.
        """
        if not index.isValid():
            return
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
            # store a pointer to the parent table in internalPointer
            return self.createIndex(row, col, self._categories[parent.row()])
        return self.createIndex(row, col, None)

    def parent(self, index):
        """Get an index to the parent of the given index.

        Override QAbstractItemModel::parent.

        Args:
            index: The QModelIndex to get the parent index for.
        """
        parent_table = index.internalPointer()
        if not parent_table:
            # categories have no parent
            return QModelIndex()
        row = self._categories.index(parent_table)
        return self.createIndex(row, 0, None)

    def rowCount(self, parent=QModelIndex()):
        if not parent.isValid():
            # top-level
            return len(self._categories)
        elif parent.internalPointer() or parent.column() != 0:
            # item or nonzero category column (only first col has children)
            return 0
        else:
            # category
            return self._categories[parent.row()].rowCount()

    def columnCount(self, parent=QModelIndex()):
        # pylint: disable=unused-argument
        return 3

    def count(self):
        """Return the count of non-category items."""
        return sum(t.rowCount() for t in self._categories)

    def set_pattern(self, pattern):
        """Set the filter pattern for all category tables.

        This will apply to the fields indicated in columns_to_filter.

        Args:
            pattern: The filter pattern to set.
        """
        log.completion.debug("Setting completion pattern '{}'".format(pattern))
        # TODO: should pattern be saved in the view layer instead?
        self.pattern = pattern
        # escape to treat a user input % or _ as a literal, not a wildcard
        pattern = pattern.replace('%', '\\%')
        pattern = pattern.replace('_', '\\_')
        # treat spaces as wildcards to match any of the typed words
        pattern = re.sub(r' +', '%', pattern)
        pattern = '%{}%'.format(pattern)
        for cat in self._categories:
            cat.set_pattern(pattern)

    def first_item(self):
        """Return the index of the first child (non-category) in the model."""
        for row, table in enumerate(self._categories):
            if table.rowCount() > 0:
                parent = self.index(row, 0)
                return self.index(0, 0, parent)
        return QModelIndex()

    def last_item(self):
        """Return the index of the last child (non-category) in the model."""
        for row, table in reversed(list(enumerate(self._categories))):
            childcount = table.rowCount()
            if childcount > 0:
                parent = self.index(row, 0)
                return self.index(childcount - 1, 0, parent)
        return QModelIndex()


class SqlException(Exception):

    """Raised on an error interacting with the SQL database."""

    pass
