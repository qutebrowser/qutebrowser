# SPDX-FileCopyrightText: Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Provides access to sqlite databases."""

import enum
import collections
import contextlib
import dataclasses
import types
from typing import Any, Dict, Iterator, List, Mapping, MutableSequence, Optional, Type, Union

from qutebrowser.qt.core import QObject, pyqtSignal
from qutebrowser.qt.sql import QSqlDatabase, QSqlError, QSqlQuery

from qutebrowser.qt import sip, machinery
from qutebrowser.utils import debug, log


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
    def from_int(cls, num: int) -> 'UserVersion':
        """Parse a number from sqlite into a major/minor user version."""
        assert 0 <= num <= 0x7FFF_FFFF, num  # signed integer, but shouldn't be negative
        major = (num & 0x7FFF_0000) >> 16
        minor = num & 0x0000_FFFF
        return cls(major, minor)

    def to_int(self) -> int:
        """Get a sqlite integer from a major/minor user version."""
        assert 0 <= self.major <= 0x7FFF  # signed integer
        assert 0 <= self.minor <= 0xFFFF
        return self.major << 16 | self.minor

    def __str__(self) -> str:
        return f'{self.major}.{self.minor}'


class SqliteErrorCode(enum.Enum):
    """Primary error codes as used by sqlite.

    See https://sqlite.org/rescode.html
    """

    # pylint: disable=invalid-name

    OK = 0  # Successful result
    ERROR = 1  # Generic error
    INTERNAL = 2  # Internal logic error in SQLite
    PERM = 3  # Access permission denied
    ABORT = 4  # Callback routine requested an abort
    BUSY = 5  # The database file is locked
    LOCKED = 6  # A table in the database is locked
    NOMEM = 7  # A malloc() failed
    READONLY = 8  # Attempt to write a readonly database
    INTERRUPT = 9  # Operation terminated by sqlite3_interrupt()*/
    IOERR = 10  # Some kind of disk I/O error occurred
    CORRUPT = 11  # The database disk image is malformed
    NOTFOUND = 12  # Unknown opcode in sqlite3_file_control()
    FULL = 13  # Insertion failed because database is full
    CANTOPEN = 14  # Unable to open the database file
    PROTOCOL = 15  # Database lock protocol error
    EMPTY = 16  # Internal use only
    SCHEMA = 17  # The database schema changed
    TOOBIG = 18  # String or BLOB exceeds size limit
    CONSTRAINT = 19  # Abort due to constraint violation
    MISMATCH = 20  # Data type mismatch
    MISUSE = 21  # Library used incorrectly
    NOLFS = 22  # Uses OS features not supported on host
    AUTH = 23  # Authorization denied
    FORMAT = 24  # Not used
    RANGE = 25  # 2nd parameter to sqlite3_bind out of range
    NOTADB = 26  # File opened that is not a database file
    NOTICE = 27  # Notifications from sqlite3_log()
    WARNING = 28  # Warnings from sqlite3_log()
    ROW = 100  # sqlite3_step() has another row ready
    DONE = 101  # sqlite3_step() has finished executing


class Error(Exception):

    """Base class for all SQL related errors."""

    def __init__(self, msg: str, error: Optional[QSqlError] = None) -> None:
        super().__init__(msg)
        self.error = error

    def text(self) -> str:
        """Get a short text description of the error.

        This is a string suitable to show to the user as error message.
        """
        if self.error is None:
            return str(self)
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


def raise_sqlite_error(msg: str, error: QSqlError) -> None:
    """Raise either a BugError or KnownError."""
    error_code = error.nativeErrorCode()
    primary_error_code: Union[SqliteErrorCode, str]
    try:
        # https://sqlite.org/rescode.html#pve
        primary_error_code = SqliteErrorCode(int(error_code) & 0xff)
    except ValueError:
        # not an int, or unknown error code -> fall back to string
        primary_error_code = error_code

    database_text = error.databaseText()
    driver_text = error.driverText()

    log.sql.debug("SQL error:")
    log.sql.debug(f"type: {debug.qenum_key(QSqlError, error.type())}")
    log.sql.debug(f"database text: {database_text}")
    log.sql.debug(f"driver text: {driver_text}")
    log.sql.debug(f"error code: {error_code} -> {primary_error_code}")

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
        primary_error_code == SqliteErrorCode.ERROR and
        (database_text.startswith("Expression tree is too large") or
         database_text in ["too many SQL variables",
                           "LIKE or GLOB pattern too complex"]))

    if primary_error_code in known_errors or too_long_err:
        raise KnownError(msg, error)

    raise BugError(msg, error)


class Database:

    """A wrapper over a QSqlDatabase connection."""

    _USER_VERSION = UserVersion(0, 4)  # The current / newest user version

    def __init__(self, path: str) -> None:
        if QSqlDatabase.database(path).isValid():
            raise BugError(f'A connection to the database at "{path}" already exists')

        self._path = path
        database = QSqlDatabase.addDatabase('QSQLITE', path)
        if not database.isValid():
            raise KnownError('Failed to add database. Are sqlite and Qt sqlite '
                             'support installed?')
        database.setDatabaseName(path)
        if not database.open():
            error = database.lastError()
            msg = f"Failed to open sqlite database at {path}: {error.text()}"
            raise_sqlite_error(msg, error)

        version_int = self.query('pragma user_version').run().value()
        self._user_version = UserVersion.from_int(version_int)

        if self._user_version.major > self._USER_VERSION.major:
            raise KnownError(
                "Database is too new for this qutebrowser version (database version "
                f"{self._user_version}, but {self._USER_VERSION.major}.x is supported)")

        if self.user_version_changed():
            # Enable write-ahead-logging and reduce disk write frequency
            # see https://sqlite.org/pragma.html and issues #2930 and #3507
            #
            # We might already have done this (without a migration) in earlier versions,
            # but as those are idempotent, let's make sure we run them once again.
            self.query("PRAGMA journal_mode=WAL").run()
            self.query("PRAGMA synchronous=NORMAL").run()

    def qt_database(self) -> QSqlDatabase:
        """Return the wrapped QSqlDatabase instance."""
        database = QSqlDatabase.database(self._path, open=True)
        if not database.isValid():
            raise BugError('Failed to get connection. Did you close() this Database '
                           'instance?')
        return database

    def query(self, querystr: str, forward_only: bool = True) -> 'Query':
        """Return a Query instance linked to this Database."""
        return Query(self, querystr, forward_only)

    def table(self, name: str, fields: List[str],
              constraints: Optional[Dict[str, str]] = None,
              parent: Optional[QObject] = None) -> 'SqlTable':
        """Return a SqlTable instance linked to this Database."""
        return SqlTable(self, name, fields, constraints, parent)

    def user_version_changed(self) -> bool:
        """Whether the version stored in the database differs from the current one."""
        return self._user_version != self._USER_VERSION

    def upgrade_user_version(self) -> None:
        """Upgrade the user version to the latest version.

        This method should be called once all required operations to migrate from one
        version to another have been run.
        """
        log.sql.debug(f"Migrating from version {self._user_version} "
                      f"to {self._USER_VERSION}")
        self.query(f'PRAGMA user_version = {self._USER_VERSION.to_int()}').run()
        self._user_version = self._USER_VERSION

    def close(self) -> None:
        """Close the SQL connection."""
        database = self.qt_database()
        database.close()
        sip.delete(database)
        QSqlDatabase.removeDatabase(self._path)

    def transaction(self) -> 'Transaction':
        """Return a Transaction object linked to this Database."""
        return Transaction(self)


class Transaction(contextlib.AbstractContextManager):  # type: ignore[type-arg]

    """A Database transaction that can be used as a context manager."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def __enter__(self) -> None:
        log.sql.debug('Starting a transaction')
        db = self._database.qt_database()
        ok = db.transaction()
        if not ok:
            error = db.lastError()
            msg = f'Failed to start a transaction: "{error.text()}"'
            raise_sqlite_error(msg, error)

    def __exit__(self,
                 _exc_type: Optional[Type[BaseException]],
                 exc_val: Optional[BaseException],
                 _exc_tb: Optional[types.TracebackType]) -> None:
        db = self._database.qt_database()
        if exc_val:
            log.sql.debug('Rolling back a transaction')
            db.rollback()
        else:
            log.sql.debug('Committing a transaction')
            ok = db.commit()
            if not ok:
                error = db.lastError()
                msg = f'Failed to commit a transaction: "{error.text()}"'
                raise_sqlite_error(msg, error)


class Query:

    """A prepared SQL query."""

    def __init__(self, database: Database, querystr: str,
                 forward_only: bool = True) -> None:
        """Prepare a new SQL query.

        Args:
            database: The Database object on which to operate.
            querystr: String to prepare query from.
            forward_only: Optimization for queries that will only step forward.
                          Must be false for completion queries.
        """
        self._database = database
        self.query = QSqlQuery(database.qt_database())

        log.sql.vdebug(f'Preparing: {querystr}')  # type: ignore[attr-defined]
        ok = self.query.prepare(querystr)
        self._check_ok('prepare', ok)
        self.query.setForwardOnly(forward_only)
        self._placeholders: List[str] = []

    def __iter__(self) -> Iterator[Any]:
        if not self.query.isActive():
            raise BugError("Cannot iterate inactive query")
        rec = self.query.record()
        fields = [rec.fieldName(i) for i in range(rec.count())]
        # pylint: disable=prefer-typing-namedtuple
        rowtype = collections.namedtuple(  # type: ignore[misc]
            'ResultRow', fields)

        while self.query.next():
            rec = self.query.record()
            yield rowtype(*[rec.value(i) for i in range(rec.count())])

    def _check_ok(self, step: str, ok: bool) -> None:
        if not ok:
            query = self.query.lastQuery()
            error = self.query.lastError()
            msg = f'Failed to {step} query "{query}": "{error.text()}"'
            raise_sqlite_error(msg, error)

    def _validate_bound_values(self) -> None:
        """Make sure all placeholders are bound."""
        qt_bound_values = self.query.boundValues()
        if machinery.IS_QT5:
            # Qt 5: Returns a dict
            values = list(qt_bound_values.values())
        else:
            # Qt 6: Returns a list
            values = qt_bound_values

        if None in values:
            raise BugError("Missing bound values!")

    def _bind_values(self, values: Mapping[str, Any]) -> Dict[str, Any]:
        self._placeholders = list(values)
        for key, val in values.items():
            self.query.bindValue(f':{key}', val)

        self._validate_bound_values()
        return self.bound_values()

    def run(self, **values: Any) -> 'Query':
        """Execute the prepared query."""
        log.sql.debug(self.query.lastQuery())

        bound_values = self._bind_values(values)
        if bound_values:
            log.sql.debug(f'    {bound_values}')

        ok = self.query.exec()
        self._check_ok('exec', ok)

        return self

    def run_batch(self, values: Mapping[str, MutableSequence[Any]]) -> None:
        """Execute the query in batch mode."""
        log.sql.debug(f'Running SQL query (batch): "{self.query.lastQuery()}"')

        self._bind_values(values)

        db = self._database.qt_database()
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

    def value(self) -> Any:
        """Return the result of a single-value query (e.g. an EXISTS)."""
        if not self.query.next():
            raise BugError("No result for single-result query")
        return self.query.record().value(0)

    def rows_affected(self) -> int:
        """Return how many rows were affected by a non-SELECT query."""
        assert not self.query.isSelect(), self
        assert self.query.isActive(), self
        rows = self.query.numRowsAffected()
        assert rows != -1
        return rows

    def bound_values(self) -> Dict[str, Any]:
        return {
            f":{key}": self.query.boundValue(f":{key}")
            for key in self._placeholders
        }


class SqlTable(QObject):

    """Interface to a SQL table.

    Attributes:
        _name: Name of the SQL table this wraps.
        database: The Database to which this table belongs.

    Signals:
        changed: Emitted when the table is modified.
    """

    changed = pyqtSignal()
    database: Database

    def __init__(self, database: Database, name: str, fields: List[str],
                 constraints: Optional[Dict[str, str]] = None,
                 parent: Optional[QObject] = None) -> None:
        """Wrapper over a table in the SQL database.

        Args:
            database: The Database to which this table belongs.
            name: Name of the table.
            fields: A list of field names.
            constraints: A dict mapping field names to constraint strings.
        """
        super().__init__(parent)
        self._name = name
        self.database = database
        self._create_table(fields, constraints)

    def _create_table(self, fields: List[str], constraints: Optional[Dict[str, str]],
                      *, force: bool = False) -> None:
        """Create the table if the database is uninitialized.

        If the table already exists, this does nothing (except with force=True), so it
        can e.g. be called on every user_version change.
        """
        if not self.database.user_version_changed() and not force:
            return

        constraints = constraints or {}
        column_defs = [f'{field} {constraints.get(field, "")}'
                       for field in fields]
        q = self.database.query(
            f"CREATE TABLE IF NOT EXISTS {self._name} ({', '.join(column_defs)})"
        )
        q.run()

    def create_index(self, name: str, field: str) -> None:
        """Create an index over this table if the database is uninitialized.

        Args:
            name: Name of the index, should be unique.
            field: Name of the field to index.
        """
        if not self.database.user_version_changed():
            return

        q = self.database.query(
            f"CREATE INDEX IF NOT EXISTS {name} ON {self._name} ({field})"
        )
        q.run()

    def __iter__(self) -> Iterator[Any]:
        """Iterate rows in the table."""
        q = self.database.query(f"SELECT * FROM {self._name}")
        q.run()
        return iter(q)

    def contains_query(self, field: str) -> Query:
        """Return a prepared query that checks for the existence of an item.

        Args:
            field: Field to match.
        """
        return self.database.query(
            f"SELECT EXISTS(SELECT * FROM {self._name} WHERE {field} = :val)"
        )

    def __len__(self) -> int:
        """Return the count of rows in the table."""
        q = self.database.query(f"SELECT count(*) FROM {self._name}")
        q.run()
        return q.value()

    def __bool__(self) -> bool:
        """Check whether there's any data in the table."""
        q = self.database.query(f"SELECT 1 FROM {self._name} LIMIT 1")
        q.run()
        return q.query.next()

    def delete(self, field: str, value: Any) -> None:
        """Remove all rows for which `field` equals `value`.

        Args:
            field: Field to use as the key.
            value: Key value to delete.
        """
        q = self.database.query(f"DELETE FROM {self._name} where {field} = :val")
        q.run(val=value)
        if not q.rows_affected():
            raise KeyError(f'No row with {field} = {value!r}')
        self.changed.emit()

    def _insert_query(self, values: Mapping[str, Any], replace: bool) -> Query:
        params = ', '.join(f':{key}' for key in values)
        columns = ', '.join(values)
        verb = "REPLACE" if replace else "INSERT"
        return self.database.query(
            f"{verb} INTO {self._name} ({columns}) values({params})"
        )

    def insert(self, values: Mapping[str, Any], replace: bool = False) -> None:
        """Append a row to the table.

        Args:
            values: A dict with a value to insert for each field name.
            replace: If set, replace existing values.
        """
        q = self._insert_query(values, replace)
        q.run(**values)
        self.changed.emit()

    def insert_batch(self, values: Mapping[str, MutableSequence[Any]],
                     replace: bool = False) -> None:
        """Performantly append multiple rows to the table.

        Args:
            values: A dict with a list of values to insert for each field name.
            replace: If true, overwrite rows with a primary key match.
        """
        q = self._insert_query(values, replace)
        q.run_batch(values)
        self.changed.emit()

    def delete_all(self) -> None:
        """Remove all rows from the table."""
        self.database.query(f"DELETE FROM {self._name}").run()
        self.changed.emit()

    def select(self, sort_by: str, sort_order: str, limit: int = -1) -> Query:
        """Prepare, run, and return a select statement on this table.

        Args:
            sort_by: name of column to sort by.
            sort_order: 'asc' or 'desc'.
            limit: max number of rows in result, defaults to -1 (unlimited).

        Return: A prepared and executed select query.
        """
        q = self.database.query(
            f"SELECT * FROM {self._name} ORDER BY {sort_by} {sort_order} LIMIT :limit"
        )
        q.run(limit=limit)
        return q


def version() -> str:
    """Return the sqlite version string."""
    try:
        with contextlib.closing(Database(':memory:')) as in_memory_db:
            return in_memory_db.query("select sqlite_version()").run().value()
    except KnownError as e:
        return f'UNAVAILABLE ({e})'
