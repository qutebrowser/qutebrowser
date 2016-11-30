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

"""The base completion model for completion in the command line.

Module attributes:
    Role: An enum of user defined model roles.
"""

import re

from PyQt5.QtCore import Qt, QModelIndex, QAbstractItemModel
from PyQt5.QtSql import QSqlTableModel, QSqlDatabase, QSqlQuery

from qutebrowser.utils import usertypes, log


Role = usertypes.enum('Role', ['sort'], start=Qt.UserRole, is_int=True)


def init():
    """Initialize the SQL completion module.

    Args:
        path: Path to the completion database.
    """
    database = QSqlDatabase.addDatabase('QSQLITE')
    # In-memory database, see https://sqlite.org/inmemorydb.html
    database.setDatabaseName(':memory:')
    if not database.open():
        raise SqlException("Failed to open in-memory sqlite database")


def close():
    """Close the SQL connection."""
    QSqlDatabase.removeDatabase(QSqlDatabase.database().connectionName())


def _run_query(querystr):
    """Run the given SQL query string on the database."""
    log.completion.debug('Running SQL query: "{}"'.format(querystr))
    database = QSqlDatabase.database('completions')
    query = QSqlQuery(database)
    if not query.exec_(querystr):
        raise SqlException('Failed to exec query "{}": "{}"'
                           .format(querystr, query.lastError().text()))


class CompletionCategory(QSqlTableModel):

    """Wraps a sql table providing data for a completion category."""

    def new_item(self, name, desc='', misc=None, sort=None):
        """Add a new item to a category.

        Fails if an item with the same name exists.

        Args:
            name: Data for the first column.
            desc: Data for the second column.
            misc: Data for the third column.
            sort: Optional data for the sorting column (not visible).
        """
        record = self.record()
        record.setValue('name', name)
        record.setValue('desc', desc)
        record.setValue('misc', misc)
        record.setValue('sort', sort)
        if not self.insertRecord(-1, record):
            raise SqlException("Failed to insert '{}': {}"
                               .format(name, self.lastError().text()))
        self.select()

    def remove_item(self, key):
        """Remove an item from a category.

        Fails if the item is not found.

        Args:
            key: The primary key value of the item to remove.
        """
        field = self.primaryKey().fieldName(0)
        _run_query("DELETE FROM {} where {} = '{}'"
                   .format(self.tableName(), field, key))
        self.select()


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
        columns_to_filter: A list of indices of columns to apply the filter to.
        pattern: Current filter pattern, used for highlighting.
        _categories: The category tables.
    """

    COLUMN_WIDTHS = (30, 50, 20)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.columns_to_filter = [0]
        self._categories = []
        self.srcmodel = self  # TODO: dummy for compat with old API
        self.pattern = ''

    def new_category(self, name, sort_by=None, sort_order=Qt.AscendingOrder,
                     primary_key='name'):
        """Create a new completion category and add it to this model.

        Args:
            name: Name of category, and the table in the database.
            sort_by: The name of the field to sort by, or None for no sorting.
            sort_order: Sorting order, if sort_by is non-None.
            primary_key: The field that is unique for each entry.

        Return: A new CompletionCategory.
        """
        _run_query("CREATE TABLE {} (name varchar, desc varchar, misc varchar,"
                   "sort int, PRIMARY KEY ({}))"
                   .format(name, primary_key))
        database = QSqlDatabase.database('completions')
        cat = CompletionCategory(parent=self, db=database)
        cat.setTable(name)
        cat.setEditStrategy(QSqlTableModel.OnFieldChange)
        if sort_by:
            cat.setSort(cat.fieldIndex(sort_by), sort_order)
        cat.select()
        self._categories.append(cat)
        return cat

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
        if not index.isValid():
            return
        if not index.parent().isValid():
            if role == Qt.DisplayRole and index.column() == 0:
                return self._categories[index.row()].tableName()
        else:
            table = self._categories[index.parent().row()]
            if role == Qt.DisplayRole:
                idx = table.index(index.row(), index.column())
                return table.data(idx)
            elif role == Role.sort:
                col = table.fieldIndex('sort')
                idx = table.index(index.row(), col)
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
        # TODO get rid of columns_to_filter once fully transitioned
        #      it is only needed in the completion item delegate for drawing
        colname = ['name', 'desc', 'misc']
        fields = [colname[c] for c in self.columns_to_filter]
        # TODO: should pattern be saved in the view layer instead?
        self.pattern = pattern
        # escape to treat a user input % or _ as a literal, not a wildcard
        pattern = pattern.replace('%', '\\%')
        pattern = pattern.replace('_', '\\_')
        # treat spaces as wildcards to match any of the typed words
        pattern = re.sub(r' +', '%', pattern)
        query = ' or '.join("{} like '%{}%' escape '\\'".format(field, pattern)
                            for field in fields)
        log.completion.debug("Setting filter = '{}'".format(query))
        for t in self._categories:
            t.setFilter(query)

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
