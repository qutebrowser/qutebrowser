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
from PyQt5.QtSql import QSqlDatabase, QSqlQuery, QSqlError

from qutebrowser.utils import log, debug


class SqlError(Exception):

    """Raised on an error interacting with the SQL database.

    Attributes:
        environmental: Whether the error is likely caused by the environment and
                       not a qutebrowser bug.
    """

    def __init__(self, msg, environmental=False):
        super().__init__(msg)
        self.environmental = environmental


class SqliteError(SqlError):

    """A SQL error with a QSqlError available.

    Attributes:
        error: The QSqlError object.
    """

    def __init__(self, msg, error):
        super().__init__(msg)
        self.error = error

        log.sql.debug("SQL error:")
        log.sql.debug("type: {}".format(
            debug.qenum_key(QSqlError, error.type())))
        log.sql.debug("database text: {}".format(error.databaseText()))
        log.sql.debug("driver text: {}".format(error.driverText()))
        log.sql.debug("error code: {}".format(error.nativeErrorCode()))

        # https://sqlite.org/rescode.html
        environmental_errors = [
            # SQLITE_LOCKED,
            # https://github.com/qutebrowser/qutebrowser/issues/2930
            '9',
            # SQLITE_FULL,
            # https://github.com/qutebrowser/qutebrowser/issues/3004
            '13',
        ]
        self.environmental = error.nativeErrorCode() in environmental_errors

    @classmethod
    def from_query(cls, what, query, error):
        """Construct an error from a failed query.

        Arguments:
            what: What we were doing when the error happened.
            query: The query which was executed.
            error: The QSqlError object.
        """
        msg = 'Failed to {} query "{}": "{}"'.format(what, query, error.text())
        return cls(msg, error)


def init(db_path):
    """Initialize the SQL database connection."""
    database = QSqlDatabase.addDatabase('QSQLITE')
    if not database.isValid():
        raise SqlError('Failed to add database. '
                       'Are sqlite and Qt sqlite support installed?',
                       environmental=True)
    database.setDatabaseName(db_path)
    if not database.open():
        error = database.lastError()
        raise SqliteError("Failed to open sqlite database at {}: {}"
                          .format(db_path, error.text()), error)


def close():
    """Close the SQL connection."""
    QSqlDatabase.removeDatabase(QSqlDatabase.database().connectionName())


def version():
    """Return the sqlite version string."""
    try:
        if not QSqlDatabase.database().isOpen():
            init(':memory:')
            ver = Query("select sqlite_version()").run().value()
            close()
            return ver
        return Query("select sqlite_version()").run().value()
    except SqlError as e:
        return 'UNAVAILABLE ({})'.format(e)


class Query(QSqlQuery):

    """A prepared SQL Query."""

    def __init__(self, querystr, forward_only=True):
        """Prepare a new sql query.

        Args:
            querystr: String to prepare query from.
            forward_only: Optimization for queries that will only step forward.
                          Must be false for completion queries.
        """
        super().__init__(QSqlDatabase.database())
        log.sql.debug('Preparing SQL query: "{}"'.format(querystr))
        if not self.prepare(querystr):
            raise SqliteError.from_query('prepare', querystr, self.lastError())
        self.setForwardOnly(forward_only)

    def __iter__(self):
        if not self.isActive():
            raise SqlError("Cannot iterate inactive query")
        rec = self.record()
        fields = [rec.fieldName(i) for i in range(rec.count())]
        rowtype = collections.namedtuple('ResultRow', fields)

        while self.next():
            rec = self.record()
            yield rowtype(*[rec.value(i) for i in range(rec.count())])

    def run(self, **values):
        """Execute the prepared query."""
        log.sql.debug('Running SQL query: "{}"'.format(self.lastQuery()))
        for key, val in values.items():
            self.bindValue(':{}'.format(key), val)
        log.sql.debug('query bindings: {}'.format(self.boundValues()))
        if not self.exec_():
            raise SqliteError.from_query('exec', self.lastQuery(),
                                         self.lastError())
        return self

    def value(self):
        """Return the result of a single-value query (e.g. an EXISTS)."""
        if not self.next():
            raise SqlError("No result for single-result query")
        return self.record().value(0)


class SqlTable(QObject):

    """Interface to a sql table.

    Attributes:
        _name: Name of the SQL table this wraps.

    Signals:
        changed: Emitted when the table is modified.
    """

    changed = pyqtSignal()

    def __init__(self, name, fields, constraints=None, parent=None):
        """Create a new table in the sql database.

        Does nothing if the table already exists.

        Args:
            name: Name of the table.
            fields: A list of field names.
            constraints: A dict mapping field names to constraint strings.
        """
        super().__init__(parent)
        self._name = name

        constraints = constraints or {}
        column_defs = ['{} {}'.format(field, constraints.get(field, ''))
                       for field in fields]
        q = Query("CREATE TABLE IF NOT EXISTS {name} ({column_defs})"
                  .format(name=name, column_defs=', '.join(column_defs)))

        q.run()

    def create_index(self, name, field):
        """Create an index over this table.

        Args:
            name: Name of the index, should be unique.
            field: Name of the field to index.
        """
        q = Query("CREATE INDEX IF NOT EXISTS {name} ON {table} ({field})"
                  .format(name=name, table=self._name, field=field))
        q.run()

    def __iter__(self):
        """Iterate rows in the table."""
        q = Query("SELECT * FROM {table}".format(table=self._name))
        q.run()
        return iter(q)

    def contains_query(self, field):
        """Return a prepared query that checks for the existence of an item.

        Args:
            field: Field to match.
        """
        return Query(
            "SELECT EXISTS(SELECT * FROM {table} WHERE {field} = :val)"
            .format(table=self._name, field=field))

    def __len__(self):
        """Return the count of rows in the table."""
        q = Query("SELECT count(*) FROM {table}".format(table=self._name))
        q.run()
        return q.value()

    def delete(self, field, value):
        """Remove all rows for which `field` equals `value`.

        Args:
            field: Field to use as the key.
            value: Key value to delete.

        Return:
            The number of rows deleted.
        """
        q = Query("DELETE FROM {table} where {field} = :val"
                  .format(table=self._name, field=field))
        q.run(val=value)
        if not q.numRowsAffected():
            raise KeyError('No row with {} = "{}"'.format(field, value))
        self.changed.emit()

    def _insert_query(self, values, replace):
        params = ', '.join(':{}'.format(key) for key in values)
        verb = "REPLACE" if replace else "INSERT"
        return Query("{verb} INTO {table} ({columns}) values({params})".format(
            verb=verb, table=self._name, columns=', '.join(values),
            params=params))

    def insert(self, values, replace=False):
        """Append a row to the table.

        Args:
            values: A dict with a value to insert for each field name.
            replace: If set, replace existing values.
        """
        q = self._insert_query(values, replace)
        q.run(**values)
        self.changed.emit()

    def insert_batch(self, values, replace=False):
        """Performantly append multiple rows to the table.

        Args:
            values: A dict with a list of values to insert for each field name.
            replace: If true, overwrite rows with a primary key match.
        """
        q = self._insert_query(values, replace)
        for key, val in values.items():
            q.bindValue(':{}'.format(key), val)

        db = QSqlDatabase.database()
        db.transaction()
        if not q.execBatch():
            raise SqliteError.from_query('exec', q.lastQuery(), q.lastError())
        db.commit()
        self.changed.emit()

    def delete_all(self):
        """Remove all rows from the table."""
        Query("DELETE FROM {table}".format(table=self._name)).run()
        self.changed.emit()

    def select(self, sort_by, sort_order, limit=-1):
        """Prepare, run, and return a select statement on this table.

        Args:
            sort_by: name of column to sort by.
            sort_order: 'asc' or 'desc'.
            limit: max number of rows in result, defaults to -1 (unlimited).

        Return: A prepared and executed select query.
        """
        q = Query("SELECT * FROM {table} ORDER BY {sort_by} {sort_order} "
                  "LIMIT :limit"
                  .format(table=self._name, sort_by=sort_by,
                          sort_order=sort_order))
        q.run(limit=limit)
        return q
