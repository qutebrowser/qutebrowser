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

"""Test the SQL API."""

import pytest
from qutebrowser.misc import sql


pytestmark = pytest.mark.usefixtures('init_sql')


def test_init():
    sql.SqlTable('Foo', ['name', 'val', 'lucky'])
    # should not error if table already exists
    sql.SqlTable('Foo', ['name', 'val', 'lucky'])


def test_insert(qtbot):
    table = sql.SqlTable('Foo', ['name', 'val', 'lucky'])
    with qtbot.waitSignal(table.changed):
        table.insert(['one', 1, False])
    with qtbot.waitSignal(table.changed):
        table.insert(['wan', 1, False])


def test_iter():
    table = sql.SqlTable('Foo', ['name', 'val', 'lucky'])
    table.insert(['one', 1, False])
    table.insert(['nine', 9, False])
    table.insert(['thirteen', 13, True])
    assert list(table) == [('one', 1, False),
                           ('nine', 9, False),
                           ('thirteen', 13, True)]


@pytest.mark.parametrize('rows, sort_by, sort_order, limit, result', [
    ([[2, 5], [1, 6], [3, 4]], 'a', 'asc', 5, [(1, 6), (2, 5), (3, 4)]),
    ([[2, 5], [1, 6], [3, 4]], 'a', 'desc', 3, [(3, 4), (2, 5), (1, 6)]),
    ([[2, 5], [1, 6], [3, 4]], 'b', 'desc', 2, [(1, 6), (2, 5)]),
    ([[2, 5], [1, 6], [3, 4]], 'a', 'asc', -1, [(1, 6), (2, 5), (3, 4)]),
])
def test_select(rows, sort_by, sort_order, limit, result):
    table = sql.SqlTable('Foo', ['a', 'b'])
    for row in rows:
        table.insert(row)
    assert list(table.select(sort_by, sort_order, limit)) == result


def test_delete(qtbot):
    table = sql.SqlTable('Foo', ['name', 'val', 'lucky'])
    table.insert(['one', 1, False])
    table.insert(['nine', 9, False])
    table.insert(['thirteen', 13, True])
    with pytest.raises(KeyError):
        table.delete('nope', 'name')
    with qtbot.waitSignal(table.changed):
        table.delete('thirteen', 'name')
    assert list(table) == [('one', 1, False), ('nine', 9, False)]
    with qtbot.waitSignal(table.changed):
        table.delete(False, field='lucky')
    assert not list(table)


def test_len():
    table = sql.SqlTable('Foo', ['name', 'val', 'lucky'])
    assert len(table) == 0
    table.insert(['one', 1, False])
    assert len(table) == 1
    table.insert(['nine', 9, False])
    assert len(table) == 2
    table.insert(['thirteen', 13, True])
    assert len(table) == 3


def test_contains():
    table = sql.SqlTable('Foo', ['name', 'val', 'lucky'])
    table.insert(['one', 1, False])
    table.insert(['nine', 9, False])
    table.insert(['thirteen', 13, True])
    assert table.contains('name', 'one')
    assert table.contains('name', 'thirteen')
    assert table.contains('val', 9)
    assert table.contains('lucky', False)
    assert table.contains('lucky', True)
    assert not table.contains('name', 'oone')
    assert not table.contains('name', 1)
    assert not table.contains('name', '*')
    assert not table.contains('val', 10)


def test_delete_all(qtbot):
    table = sql.SqlTable('Foo', ['name', 'val', 'lucky'])
    table.insert(['one', 1, False])
    table.insert(['nine', 9, False])
    table.insert(['thirteen', 13, True])
    with qtbot.waitSignal(table.changed):
        table.delete_all()
    assert list(table) == []


def test_version():
    assert isinstance(sql.version(), str)
