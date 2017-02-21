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

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtSql import QSqlDatabase, QSqlQuery

from qutebrowser.utils import log

import collections


class SqlException(Exception):

    """Raised on an error interacting with the SQL database."""

    pass


def init():
    """Initialize the SQL database connection."""
    database = QSqlDatabase.addDatabase('QSQLITE')
    # In-memory database, see https://sqlite.org/inmemorydb.html
    database.setDatabaseName(':memory:')
    if not database.open():
        raise SqlException("Failed to open in-memory sqlite database: {}"
                           .format(database.lastError().text()))


def close():
    """Close the SQL connection."""
    QSqlDatabase.removeDatabase(QSqlDatabase.database().connectionName())


def version():
    """Return the sqlite version string."""
    result = run_query("select sqlite_version()")
    result.next()
    return result.record().value(0)


def run_query(querystr, values=None):
    """Run the given SQL query string on the database.

    Args:
        values: A list of positional parameter bindings.
    """
    log.sql.debug('Running SQL query: "{}"'.format(querystr))
    database = QSqlDatabase.database()
    query = QSqlQuery(database)
    query.prepare(querystr)
    for val in values or []:
        query.addBindValue(val)
    log.sql.debug('Query bindings: {}'.format(query.boundValues()))
    if not query.exec_():
        raise SqlException('Failed to exec query "{}": "{}"'.format(
                           querystr, query.lastError().text()))
    return query


class SqlTable(QObject):

    """Interface to a sql table.

    Attributes:
        Entry: The class wrapping row data from this table.
        _name: Name of the SQL table this wraps.
        _primary_key: The primary key of the table.

    Signals:
        changed: Emitted when the table is modified.
    """

    changed = pyqtSignal()

    def __init__(self, name, fields, primary_key, parent=None):
        """Create a new table in the sql database.

        Raises SqlException if the table already exists.

        Args:
            name: Name of the table.
            fields: A list of field names.
            primary_key: Name of the field to serve as the primary key.
        """
        super().__init__(parent)
        self._name = name
        self._primary_key = primary_key
        run_query("CREATE TABLE {} ({}, PRIMARY KEY ({}))".format(
            name, ','.join(fields), primary_key))
        # pylint: disable=invalid-name
        self.Entry = collections.namedtuple(name + '_Entry', fields)

    def __iter__(self):
        """Iterate rows in the table."""
        result = run_query("SELECT * FROM {}".format(self._name))
        while result.next():
            rec = result.record()
            yield self.Entry(*[rec.value(i) for i in range(rec.count())])

    def __contains__(self, key):
        """Return whether the table contains the matching item.

        Args:
            key: Primary key value to search for.
        """
        query = run_query("SELECT * FROM {} where {} = ?".format(
            self._name, self._primary_key), [key])
        return query.next()

    def __len__(self):
        """Return the count of rows in the table."""
        result = run_query("SELECT count(*) FROM {}".format(self._name))
        result.next()
        return result.value(0)

    def __getitem__(self, key):
        """Retrieve the row matching the given key.

        Args:
            key: Primary key value to fetch.
        """
        result = run_query("SELECT * FROM {} where {} = ?".format(
            self._name, self._primary_key), [key])
        result.next()
        rec = result.record()
        return self.Entry(*[rec.value(i) for i in range(rec.count())])

    def delete(self, value, field=None):
        """Remove all rows for which `field` equals `value`.

        Args:
            value: Key value to delete.
            field: Field to use as the key, defaults to the primary key.

        Return:
            The number of rows deleted.
        """
        field = field or self._primary_key
        query = run_query("DELETE FROM {} where {} = ?".format(
            self._name, field), [value])
        if not query.numRowsAffected():
            raise KeyError('No row with {} = "{}"'.format(field, value))
        self.changed.emit()

    def insert(self, values, replace=False):
        """Append a row to the table.

        Args:
            values: A list of values to insert.
            replace: If true, allow inserting over an existing primary key.
        """
        cmd = "REPLACE" if replace else "INSERT"
        paramstr = ','.join(['?'] * len(values))
        run_query("{} INTO {} values({})".format(cmd, self._name, paramstr),
            values)
        self.changed.emit()

    def delete_all(self):
        """Remove all row from the table."""
        run_query("DELETE FROM {}".format(self._name))
        self.changed.emit()
