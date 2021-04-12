# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2021 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Provides access to an in-memory sqlite database."""

import collections
import dataclasses

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtSql import QSqlDatabase, QSqlQuery, QSqlError

from qutebrowser.utils import log, debug


@dataclasses.dataclass
class UserVersion:

    """The version of data stored in the history database.

    When we originally started using user_version, we only used it to signify that the
    completion database should be regenerated. However, sometimes there are
    backwards-incompatible changes.

    Instead, we now (ab)use the fact that the user_version in sqlite is a 32-bit integer
    to store both a major and a minor part. If only the minor part changed, we can deal
    with it (there are only new URLs to clean up or somesuch). If the major part
    changed, there are backwards-incompatible changes in how the database works, so
    newer databases are not compatible with older qutebrowser versions.
    """

    major: int
    minor: int

    @classmethod
    def from_int(cls, num):
        """Parse a number from sqlite into a major/minor user version."""
        assert 0 <= num <= 0x7FFF_FFFF, num  # signed integer, but shouldn't be negative
        major = (num & 0x7FFF_0000) >> 16
        minor = num & 0x0000_FFFF
        return cls(major, minor)

    def to_int(self):
        """Get a sqlite integer from a major/minor user version."""
        assert 0 <= self.major <= 0x7FFF  # signed integer
        assert 0 <= self.minor <= 0xFFFF
        return self.major << 16 | self.minor

    def __str__(self):
        return f'{self.major}.{self.minor}'


_db_user_version = None   # The user version we got from the database
_USER_VERSION = UserVersion(0, 4)    # The current / newest user version


def user_version_changed():
    """Whether the version stored in the database is different from the current one."""
    return _db_user_version != _USER_VERSION


class SqliteErrorCode:

    """Error codes as used by sqlite.

    See https://sqlite.org/rescode.html - note we only define the codes we use
    in qutebrowser here.
    """

    ERROR = '1'  # generic error code
    BUSY = '5'  # database is locked
    READONLY = '8'  # attempt to write a readonly database
    IOERR = '10'  # disk I/O error
    CORRUPT = '11'  # database disk image is malformed
    FULL = '13'  # database or disk is full
    CANTOPEN = '14'  # unable to open database file
    PROTOCOL = '15'  # locking protocol error
    CONSTRAINT = '19'  # UNIQUE constraint failed
    NOTADB = '26'  # file is not a database


class Error(Exception):

    """Base class for all SQL related errors."""

    def __init__(self, msg, error=None):
        super().__init__(msg)
        self.error = error

    def text(self):
        """Get a short text description of the error.

        This is a string suitable to show to the user as error message.
        """
        if self.error is None:
            return str(self)
        else:
            return self.error.databaseText()


class KnownError(Error):

    """Raised on an error interacting with the SQL database.

    This is raised in conditions resulting from the environment (like a full
    disk or I/O errors), where qutebrowser isn't to blame.
    """


class BugError(Error):

    """Raised on an error interacting with the SQL database.

    This is raised for errors resulting from a qutebrowser bug.
    """


def raise_sqlite_error(msg, error):
    """Raise either a BugError or KnownError."""
    error_code = error.nativeErrorCode()
    database_text = error.databaseText()
    driver_text = error.driverText()

    log.sql.debug("SQL error:")
    log.sql.debug("type: {}".format(
        debug.qenum_key(QSqlError, error.type())))
    log.sql.debug("database text: {}".format(database_text))
    log.sql.debug("driver text: {}".format(driver_text))
    log.sql.debug("error code: {}".format(error_code))

    known_errors = [
        SqliteErrorCode.BUSY,
        SqliteErrorCode.READONLY,
        SqliteErrorCode.IOERR,
        SqliteErrorCode.CORRUPT,
        SqliteErrorCode.FULL,
        SqliteErrorCode.CANTOPEN,
        SqliteErrorCode.PROTOCOL,
        SqliteErrorCode.NOTADB,
    ]

    # https://github.com/qutebrowser/qutebrowser/issues/4681
    # If the query we built was too long
    too_long_err = (
        error_code == SqliteErrorCode.ERROR and
        (database_text.startswith("Expression tree is too large") or
         database_text in ["too many SQL variables",
                           "LIKE or GLOB pattern too complex"]))

    if error_code in known_errors or too_long_err:
        raise KnownError(msg, error)

    raise BugError(msg, error)


def init(db_path):
    """Initialize the SQL database connection."""
    database = QSqlDatabase.addDatabase('QSQLITE')
    if not database.isValid():
        raise KnownError('Failed to add database. Are sqlite and Qt sqlite '
                         'support installed?')
    database.setDatabaseName(db_path)
    if not database.open():
        error = database.lastError()
        msg = "Failed to open sqlite database at {}: {}".format(db_path,
                                                                error.text())
        raise_sqlite_error(msg, error)

    global _db_user_version
    version_int = Query('pragma user_version').run().value()
    _db_user_version = UserVersion.from_int(version_int)

    if _db_user_version.major > _USER_VERSION.major:
        raise KnownError(
            "Database is too new for this qutebrowser version (database version "
            f"{_db_user_version}, but {_USER_VERSION.major}.x is supported)")

    if user_version_changed():
        log.sql.debug(f"Migrating from version {_db_user_version} to {_USER_VERSION}")
        # Note we're *not* updating the _db_user_version global here. We still want
        # user_version_changed() to return True, as other modules (such as history.py)
        # use it to create the initial table structure.
        Query(f'PRAGMA user_version = {_USER_VERSION.to_int()}').run()

        # Enable write-ahead-logging and reduce disk write frequency
        # see https://sqlite.org/pragma.html and issues #2930 and #3507
        #
        # We might already have done this (without a migration) in earlier versions, but
        # as those are idempotent, let's make sure we run them once again.
        Query("PRAGMA journal_mode=WAL").run()
        Query("PRAGMA synchronous=NORMAL").run()


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
    except KnownError as e:
        return 'UNAVAILABLE ({})'.format(e)


class Query:

    """A prepared SQL query."""

    def __init__(self, querystr, forward_only=True):
        """Prepare a new SQL query.

        Args:
            querystr: String to prepare query from.
            forward_only: Optimization for queries that will only step forward.
                          Must be false for completion queries.
        """
        self.query = QSqlQuery(QSqlDatabase.database())

        log.sql.vdebug(f'Preparing: {querystr}')  # type: ignore[attr-defined]
        ok = self.query.prepare(querystr)
        self._check_ok('prepare', ok)
        self.query.setForwardOnly(forward_only)

    def __iter__(self):
        if not self.query.isActive():
            raise BugError("Cannot iterate inactive query")
        rec = self.query.record()
        fields = [rec.fieldName(i) for i in range(rec.count())]
        rowtype = collections.namedtuple(  # type: ignore[misc]
            'ResultRow', fields)

        while self.query.next():
            rec = self.query.record()
            yield rowtype(*[rec.value(i) for i in range(rec.count())])

    def _check_ok(self, step, ok):
        if not ok:
            query = self.query.lastQuery()
            error = self.query.lastError()
            msg = 'Failed to {} query "{}": "{}"'.format(step, query,
                                                         error.text())
            raise_sqlite_error(msg, error)

    def _bind_values(self, values):
        for key, val in values.items():
            self.query.bindValue(':{}'.format(key), val)

        bound_values = self.bound_values()
        if None in bound_values.values():
            raise BugError("Missing bound values!")

        return bound_values

    def run(self, **values):
        """Execute the prepared query."""
        log.sql.debug(self.query.lastQuery())

        bound_values = self._bind_values(values)
        if bound_values:
            log.sql.debug(f'    {bound_values}')

        ok = self.query.exec()
        self._check_ok('exec', ok)

        return self

    def run_batch(self, values):
        """Execute the query in batch mode."""
        log.sql.debug('Running SQL query (batch): "{}"'.format(
            self.query.lastQuery()))

        self._bind_values(values)

        db = QSqlDatabase.database()
        ok = db.transaction()
        self._check_ok('transaction', ok)

        ok = self.query.execBatch()
        try:
            self._check_ok('execBatch', ok)
        except Error:
            # Not checking the return value here, as we're failing anyways...
            db.rollback()
            raise

        ok = db.commit()
        self._check_ok('commit', ok)

    def value(self):
        """Return the result of a single-value query (e.g. an EXISTS)."""
        if not self.query.next():
            raise BugError("No result for single-result query")
        return self.query.record().value(0)

    def rows_affected(self):
        """Return how many rows were affected by a non-SELECT query."""
        assert not self.query.isSelect(), self
        assert self.query.isActive(), self
        rows = self.query.numRowsAffected()
        assert rows != -1
        return rows

    def bound_values(self):
        return self.query.boundValues()


class SqlTable(QObject):

    """Interface to a SQL table.

    Attributes:
        _name: Name of the SQL table this wraps.

    Signals:
        changed: Emitted when the table is modified.
    """

    changed = pyqtSignal()

    def __init__(self, name, fields, constraints=None, parent=None):
        """Wrapper over a table in the SQL database.

        Args:
            name: Name of the table.
            fields: A list of field names.
            constraints: A dict mapping field names to constraint strings.
        """
        super().__init__(parent)
        self._name = name
        self._create_table(fields, constraints)

    def _create_table(self, fields, constraints, *, force=False):
        """Create the table if the database is uninitialized.

        If the table already exists, this does nothing (except with force=True), so it
        can e.g. be called on every user_version change.
        """
        if not user_version_changed() and not force:
            return

        constraints = constraints or {}
        column_defs = ['{} {}'.format(field, constraints.get(field, ''))
                       for field in fields]
        q = Query("CREATE TABLE IF NOT EXISTS {name} ({column_defs})"
                  .format(name=self._name, column_defs=', '.join(column_defs)))
        q.run()

    def create_index(self, name, field):
        """Create an index over this table if the database is uninitialized.

        Args:
            name: Name of the index, should be unique.
            field: Name of the field to index.
        """
        if not user_version_changed():
            return

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

    def __bool__(self):
        """Check whether there's any data in the table."""
        q = Query(f"SELECT 1 FROM {self._name} LIMIT 1")
        q.run()
        return q.query.next()

    def delete(self, field, value):
        """Remove all rows for which `field` equals `value`.

        Args:
            field: Field to use as the key.
            value: Key value to delete.

        Return:
            The number of rows deleted.
        """
        q = Query(f"DELETE FROM {self._name} where {field} = :val")
        q.run(val=value)
        if not q.rows_affected():
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
        q.run_batch(values)
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
