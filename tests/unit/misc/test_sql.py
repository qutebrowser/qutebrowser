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

"""Test the SQL API."""

import pytest

import hypothesis
from hypothesis import strategies
from PyQt5.QtSql import QSqlDatabase, QSqlError, QSqlQuery

from qutebrowser.misc import sql


pytestmark = pytest.mark.usefixtures('data_tmpdir')


@pytest.fixture
def db(data_tmpdir):
    database = sql.Database(str(data_tmpdir / 'test_sql.db'))
    return database


class TestUserVersion:

    @pytest.mark.parametrize('val, major, minor', [
        (0x0008_0001, 8, 1),
        (0x7FFF_FFFF, 0x7FFF, 0xFFFF),
    ])
    def test_from_int(self, val, major, minor):
        version = sql.UserVersion.from_int(val)
        assert version.major == major
        assert version.minor == minor

    @pytest.mark.parametrize('major, minor, val', [
        (8, 1, 0x0008_0001),
        (0x7FFF, 0xFFFF, 0x7FFF_FFFF),
    ])
    def test_to_int(self, major, minor, val):
        version = sql.UserVersion(major, minor)
        assert version.to_int() == val

    @pytest.mark.parametrize('val', [0x8000_0000, -1])
    def test_from_int_invalid(self, val):
        with pytest.raises(AssertionError):
            sql.UserVersion.from_int(val)

    @pytest.mark.parametrize('major, minor', [
        (-1, 0),
        (0, -1),
        (0, 0x10000),
        (0x8000, 0),
    ])
    def test_to_int_invalid(self, major, minor):
        version = sql.UserVersion(major, minor)
        with pytest.raises(AssertionError):
            version.to_int()

    @hypothesis.given(val=strategies.integers(min_value=0, max_value=0x7FFF_FFFF))
    def test_from_int_hypothesis(self, val):
        version = sql.UserVersion.from_int(val)
        assert version.to_int() == val

    @hypothesis.given(
        major=strategies.integers(min_value=0, max_value=0x7FFF),
        minor=strategies.integers(min_value=0, max_value=0xFFFF)
    )
    def test_to_int_hypothesis(self, major, minor):
        version = sql.UserVersion(major, minor)
        assert version.from_int(version.to_int()) == version


@pytest.mark.parametrize('klass', [sql.KnownError, sql.BugError])
def test_sqlerror(klass):
    text = "Hello World"
    err = klass(text)
    assert str(err) == text
    assert err.text() == text


class TestSqlError:

    @pytest.mark.parametrize('error_code, exception', [
        (sql.SqliteErrorCode.BUSY, sql.KnownError),
        (sql.SqliteErrorCode.CONSTRAINT, sql.BugError),
    ])
    def test_known(self, error_code, exception):
        sql_err = QSqlError("driver text", "db text", QSqlError.UnknownError,
                            error_code)
        with pytest.raises(exception):
            sql.raise_sqlite_error("Message", sql_err)

    def test_logging(self, caplog):
        sql_err = QSqlError("driver text", "db text", QSqlError.UnknownError, '23')
        with pytest.raises(sql.BugError):
            sql.raise_sqlite_error("Message", sql_err)

        expected = ['SQL error:',
                    'type: UnknownError',
                    'database text: db text',
                    'driver text: driver text',
                    'error code: 23']

        assert caplog.messages == expected

    @pytest.mark.parametrize('klass', [sql.KnownError, sql.BugError])
    def test_text(self, klass):
        sql_err = QSqlError("driver text", "db text")
        err = klass("Message", sql_err)
        assert err.text() == "db text"


def test_init_table(db):
    db.table('Foo', ['name', 'val', 'lucky'])
    # should not error if table already exists
    db.table('Foo', ['name', 'val', 'lucky'])


def test_insert(qtbot, db):
    table = db.table('Foo', ['name', 'val', 'lucky'])
    with qtbot.wait_signal(table.changed):
        table.insert({'name': 'one', 'val': 1, 'lucky': False})
    with qtbot.wait_signal(table.changed):
        table.insert({'name': 'wan', 'val': 1, 'lucky': False})


def test_insert_replace(qtbot, db):
    table = db.table('Foo', ['name', 'val', 'lucky'],
                     constraints={'name': 'PRIMARY KEY'})
    with qtbot.wait_signal(table.changed):
        table.insert({'name': 'one', 'val': 1, 'lucky': False}, replace=True)
    with qtbot.wait_signal(table.changed):
        table.insert({'name': 'one', 'val': 11, 'lucky': True}, replace=True)
    assert list(table) == [('one', 11, True)]

    with pytest.raises(sql.BugError):
        table.insert({'name': 'one', 'val': 11, 'lucky': True}, replace=False)


def test_insert_batch(qtbot, db):
    table = db.table('Foo', ['name', 'val', 'lucky'])

    with qtbot.wait_signal(table.changed):
        table.insert_batch({'name': ['one', 'nine', 'thirteen'],
                            'val': [1, 9, 13],
                            'lucky': [False, False, True]})

    assert list(table) == [('one', 1, False),
                           ('nine', 9, False),
                           ('thirteen', 13, True)]


def test_insert_batch_replace(qtbot, db):
    table = db.table('Foo', ['name', 'val', 'lucky'],
                     constraints={'name': 'PRIMARY KEY'})

    with qtbot.wait_signal(table.changed):
        table.insert_batch({'name': ['one', 'nine', 'thirteen'],
                            'val': [1, 9, 13],
                            'lucky': [False, False, True]})

    with qtbot.wait_signal(table.changed):
        table.insert_batch({'name': ['one', 'nine'],
                            'val': [11, 19],
                            'lucky': [True, True]},
                           replace=True)

    assert list(table) == [('thirteen', 13, True),
                           ('one', 11, True),
                           ('nine', 19, True)]

    with pytest.raises(sql.BugError):
        table.insert_batch({'name': ['one', 'nine'],
                            'val': [11, 19],
                            'lucky': [True, True]})


def test_iter(db):
    table = db.table('Foo', ['name', 'val', 'lucky'])
    table.insert({'name': 'one', 'val': 1, 'lucky': False})
    table.insert({'name': 'nine', 'val': 9, 'lucky': False})
    table.insert({'name': 'thirteen', 'val': 13, 'lucky': True})
    assert list(table) == [('one', 1, False),
                           ('nine', 9, False),
                           ('thirteen', 13, True)]


@pytest.mark.parametrize('rows, sort_by, sort_order, limit, result', [
    ([{"a": 2, "b": 5}, {"a": 1, "b": 6}, {"a": 3, "b": 4}], 'a', 'asc', 5,
     [(1, 6), (2, 5), (3, 4)]),
    ([{"a": 2, "b": 5}, {"a": 1, "b": 6}, {"a": 3, "b": 4}], 'a', 'desc', 3,
     [(3, 4), (2, 5), (1, 6)]),
    ([{"a": 2, "b": 5}, {"a": 1, "b": 6}, {"a": 3, "b": 4}], 'b', 'desc', 2,
     [(1, 6), (2, 5)]),
    ([{"a": 2, "b": 5}, {"a": 1, "b": 6}, {"a": 3, "b": 4}], 'a', 'asc', -1,
     [(1, 6), (2, 5), (3, 4)]),
])
def test_select(rows, sort_by, sort_order, limit, result, db):
    table = db.table('Foo', ['a', 'b'])
    for row in rows:
        table.insert(row)
    assert list(table.select(sort_by, sort_order, limit)) == result


def test_delete(qtbot, db):
    table = db.table('Foo', ['name', 'val', 'lucky'])
    table.insert({'name': 'one', 'val': 1, 'lucky': False})
    table.insert({'name': 'nine', 'val': 9, 'lucky': False})
    table.insert({'name': 'thirteen', 'val': 13, 'lucky': True})
    with pytest.raises(KeyError):
        table.delete('name', 'nope')
    with qtbot.wait_signal(table.changed):
        table.delete('name', 'thirteen')
    assert list(table) == [('one', 1, False), ('nine', 9, False)]
    with qtbot.wait_signal(table.changed):
        table.delete('lucky', False)
    assert not list(table)


def test_len(db):
    table = db.table('Foo', ['name', 'val', 'lucky'])
    assert len(table) == 0
    table.insert({'name': 'one', 'val': 1, 'lucky': False})
    assert len(table) == 1
    table.insert({'name': 'nine', 'val': 9, 'lucky': False})
    assert len(table) == 2
    table.insert({'name': 'thirteen', 'val': 13, 'lucky': True})
    assert len(table) == 3


def test_bool(db):
    table = db.table('Foo', ['name'])
    assert not table
    table.insert({'name': 'one'})
    assert table


def test_bool_benchmark(benchmark, db):
    table = db.table('Foo', ['number'])

    # Simulate a history table
    table.create_index('NumberIndex', 'number')
    table.insert_batch({'number': [str(i) for i in range(100_000)]})

    def run():
        assert table

    benchmark(run)


def test_contains(db):
    table = db.table('Foo', ['name', 'val', 'lucky'])
    table.insert({'name': 'one', 'val': 1, 'lucky': False})
    table.insert({'name': 'nine', 'val': 9, 'lucky': False})
    table.insert({'name': 'thirteen', 'val': 13, 'lucky': True})

    name_query = table.contains_query('name')
    val_query = table.contains_query('val')
    lucky_query = table.contains_query('lucky')

    assert name_query.run(val='one').value()
    assert name_query.run(val='thirteen').value()
    assert val_query.run(val=9).value()
    assert lucky_query.run(val=False).value()
    assert lucky_query.run(val=True).value()
    assert not name_query.run(val='oone').value()
    assert not name_query.run(val=1).value()
    assert not name_query.run(val='*').value()
    assert not val_query.run(val=10).value()


def test_delete_all(qtbot, db):
    table = db.table('Foo', ['name', 'val', 'lucky'])
    table.insert({'name': 'one', 'val': 1, 'lucky': False})
    table.insert({'name': 'nine', 'val': 9, 'lucky': False})
    table.insert({'name': 'thirteen', 'val': 13, 'lucky': True})
    with qtbot.wait_signal(table.changed):
        table.delete_all()
    assert list(table) == []


def test_version():
    assert isinstance(sql.version(), str)


class TestSqlQuery:

    def test_prepare_error(self, db):
        with pytest.raises(sql.BugError) as excinfo:
            db.query('invalid')

        expected = ('Failed to prepare query "invalid": "near "invalid": '
                    'syntax error Unable to execute statement"')
        assert str(excinfo.value) == expected

    @pytest.mark.parametrize('forward_only', [True, False])
    def test_forward_only(self, forward_only, db):
        q = db.query('SELECT 0 WHERE 0', forward_only=forward_only)
        assert q.query.isForwardOnly() == forward_only

    def test_iter_inactive(self, db):
        q = db.query('SELECT 0')
        with pytest.raises(sql.BugError,
                           match='Cannot iterate inactive query'):
            next(iter(q))

    def test_iter_empty(self, db):
        q = db.query('SELECT 0 AS col WHERE 0')
        q.run()
        with pytest.raises(StopIteration):
            next(iter(q))

    def test_iter(self, db):
        q = db.query('SELECT 0 AS col')
        q.run()
        result = next(iter(q))
        assert result.col == 0

    def test_iter_multiple(self, db):
        q = db.query('VALUES (1), (2), (3);')
        res = list(q.run())
        assert len(res) == 3
        assert res[0].column1 == 1

    def test_run_binding(self, db):
        q = db.query('SELECT :answer')
        q.run(answer=42)
        assert q.value() == 42

    def test_run_missing_binding(self, db):
        q = db.query('SELECT :answer')
        with pytest.raises(sql.BugError, match='Missing bound values!'):
            q.run()

    def test_run_batch(self, db):
        q = db.query('SELECT :answer')
        q.run_batch(values={'answer': [42]})
        assert q.value() == 42

    def test_run_batch_missing_binding(self, db):
        q = db.query('SELECT :answer')
        with pytest.raises(sql.BugError, match='Missing bound values!'):
            q.run_batch(values={})

    def test_value_missing(self, db):
        q = db.query('SELECT 0 WHERE 0')
        q.run()
        with pytest.raises(sql.BugError, match='No result for single-result query'):
            q.value()

    def test_num_rows_affected_not_active(self, db):
        with pytest.raises(AssertionError):
            q = db.query('SELECT 0')
            q.rows_affected()

    def test_num_rows_affected_select(self, db):
        with pytest.raises(AssertionError):
            q = db.query('SELECT 0')
            q.run()
            q.rows_affected()

    @pytest.mark.parametrize('condition', [0, 1])
    def test_num_rows_affected(self, condition, db):
        table = db.table('Foo', ['name'])
        table.insert({'name': 'helloworld'})
        q = db.query(f'DELETE FROM Foo WHERE {condition}')
        q.run()
        assert q.rows_affected() == condition

    def test_bound_values(self, db):
        q = db.query('SELECT :answer')
        q.run(answer=42)
        assert q.bound_values() == {':answer': 42}


class TestTransaction:

    def test_successful_transaction(self, db):
        my_table = db.table('my_table', ['column'])
        with db.transaction():
            my_table.insert({'column': 1})
            my_table.insert({'column': 2})

            db2 = QSqlDatabase.addDatabase('QSQLITE', 'db2')
            db2.setDatabaseName(db.qt_database().databaseName())
            db2.open()
            query = QSqlQuery(db2)
            query.exec('select count(*) from my_table')
            query.next()
            assert query.record().value(0) == 0
        assert db.query('select count(*) from my_table').run().value() == 2

    def test_failed_transaction(self, db):
        my_table = db.table('my_table', ['column'])
        try:
            with db.transaction():
                my_table.insert({'column': 1})
                my_table.insert({'column': 2})
                raise Exception('something went horribly wrong')
        except Exception:
            pass
        assert db.query('select count(*) from my_table').run().value() == 0
