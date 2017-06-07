# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2017 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""Provides access to an in-memory sqlite database."""

import collections

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtSql import QSqlDatabase, QSqlQuery

from qutebrowser.utils import log


class SqlException(Exception):

    """Raised on an error interacting with the SQL database."""

    pass


def init(db_path):
    """Initialize the SQL database connection."""
    database = QSqlDatabase.addDatabase('QSQLITE')
    database.setDatabaseName(db_path)
    if not database.open():
        raise SqlException("Failed to open sqlite database at {}: {}"
                           .format(db_path, database.lastError().text()))


def close():
    """Close the SQL connection."""
    QSqlDatabase.removeDatabase(QSqlDatabase.database().connectionName())


def version():
    """Return the sqlite version string."""
    q = Query("select sqlite_version()")
    q.run()
    return q.value()


class Query(QSqlQuery):

    """A prepared SQL Query."""

    def __init__(self, querystr):
        super().__init__(QSqlDatabase.database())
        log.sql.debug('Preparing SQL query: "{}"'.format(querystr))
        self.prepare(querystr)

    def __iter__(self):
        assert self.isActive(), "Cannot iterate inactive query"
        rec = self.record()
        fields = [rec.fieldName(i) for i in range(rec.count())]
        rowtype = collections.namedtuple('ResultRow', fields)

        while self.next():
            rec = self.record()
            yield rowtype(*[rec.value(i) for i in range(rec.count())])

    def run(self, values=None):
        """Execute the prepared query."""
        log.sql.debug('Running SQL query: "{}"'.format(self.lastQuery()))
        for val in values or []:
            self.addBindValue(val)
        log.sql.debug('self bindings: {}'.format(self.boundValues()))
        if not self.exec_():
            raise SqlException('Failed to exec query "{}": "{}"'.format(
                               self.lastQuery(), self.lastError().text()))
        return self

    def value(self):
        """Return the result of a single-value query (e.g. an EXISTS)."""
        ok = self.next()
        assert ok, "No result for single-result query"
        return self.record().value(0)


class SqlTable(QObject):

    """Interface to a sql table.

    Attributes:
        Entry: The class wrapping row data from this table.
        _name: Name of the SQL table this wraps.

    Signals:
        changed: Emitted when the table is modified.
    """

    changed = pyqtSignal()

    def __init__(self, name, fields, parent=None):
        """Create a new table in the sql database.

        Raises SqlException if the table already exists.

        Args:
            name: Name of the table.
            fields: A list of field names.
        """
        super().__init__(parent)
        self._name = name
        q = Query("CREATE TABLE IF NOT EXISTS {} ({})"
                  .format(name, ','.join(fields)))
        q.run()
        # pylint: disable=invalid-name
        self.Entry = collections.namedtuple(name + '_Entry', fields)

    def create_index(self, name, field):
        """Create an index over this table.

        Args:
            name: Name of the index, should be unique.
            field: Name of the field to index.
        """
        q = Query("CREATE INDEX IF NOT EXISTS {} ON {} ({})"
                  .format(name, self._name, field))
        q.run()

    def __iter__(self):
        """Iterate rows in the table."""
        q = Query("SELECT * FROM {}".format(self._name))
        q.run()
        return iter(q)

    def contains_query(self, field):
        """Return a prepared query that checks for the existence of an item.

        Args:
            field: Field to match.
        """
        return Query("Select EXISTS(SELECT * FROM {} where {} = ?)"
                     .format(self._name, field))

    def __len__(self):
        """Return the count of rows in the table."""
        q = Query("SELECT count(*) FROM {}".format(self._name))
        q.run()
        return q.value()

    def delete(self, value, field):
        """Remove all rows for which `field` equals `value`.

        Args:
            value: Key value to delete.
            field: Field to use as the key.

        Return:
            The number of rows deleted.
        """
        q = Query("DELETE FROM {} where {} = ?".format(self._name, field))
        q.run([value])
        if not q.numRowsAffected():
            raise KeyError('No row with {} = "{}"'.format(field, value))
        self.changed.emit()

    def insert(self, values):
        """Append a row to the table.

        Args:
            values: A list of values to insert.
        """
        paramstr = ','.join(['?'] * len(values))
        q = Query("INSERT INTO {} values({})".format(self._name, paramstr))
        q.run(values)
        self.changed.emit()

    def insert_batch(self, rows):
        """Performantly append multiple rows to the table.

        Args:
            rows: A list of lists, where each sub-list is a row.
        """
        paramstr = ','.join(['?'] * len(rows[0]))
        q = Query("INSERT INTO {} values({})".format(self._name, paramstr))

        transposed = [list(row) for row in zip(*rows)]
        for val in transposed:
            q.addBindValue(val)

        db = QSqlDatabase.database()
        db.transaction()
        if not q.execBatch():
            raise SqlException('Failed to exec query "{}": "{}"'.format(
                               q.lastQuery(), q.lastError().text()))
        db.commit()
        self.changed.emit()

    def delete_all(self):
        """Remove all row from the table."""
        Query("DELETE FROM {}".format(self._name)).run()
        self.changed.emit()

    def select(self, sort_by, sort_order, limit=-1):
        """Remove all row from the table.

        Args:
            sort_by: name of column to sort by.
            sort_order: 'asc' or 'desc'.
            limit: max number of rows in result, defaults to -1 (unlimited).
        """
        q = Query('SELECT * FROM {} ORDER BY {} {} LIMIT ?'
                  .format(self._name, sort_by, sort_order))
        q.run([limit])
        return q
