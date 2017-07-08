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

"""Test SQL-based completions."""

import unittest.mock

import pytest

from qutebrowser.misc import sql
from qutebrowser.completion.models import sqlcategory
from qutebrowser.commands import cmdexc


pytestmark = pytest.mark.usefixtures('init_sql')


@pytest.mark.parametrize('sort_by, sort_order, data, expected', [
    (None, 'asc',
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')]),

    ('a', 'asc',
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('A', 'F', 'C'), ('B', 'C', 'D'), ('C', 'A', 'G')]),

    ('a', 'desc',
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('C', 'A', 'G'), ('B', 'C', 'D'), ('A', 'F', 'C')]),

    ('b', 'asc',
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('C', 'A', 'G'), ('B', 'C', 'D'), ('A', 'F', 'C')]),

    ('b', 'desc',
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('A', 'F', 'C'), ('B', 'C', 'D'), ('C', 'A', 'G')]),

    ('c', 'asc',
     [('B', 'C', 2), ('A', 'F', 0), ('C', 'A', 1)],
     [('A', 'F', 0), ('C', 'A', 1), ('B', 'C', 2)]),

    ('c', 'desc',
     [('B', 'C', 2), ('A', 'F', 0), ('C', 'A', 1)],
     [('B', 'C', 2), ('C', 'A', 1), ('A', 'F', 0)]),
])
def test_sorting(sort_by, sort_order, data, expected, validate_model):
    table = sql.SqlTable('Foo', ['a', 'b', 'c'])
    for row in data:
        table.insert({'a': row[0], 'b': row[1], 'c': row[2]})
    cat = sqlcategory.SqlCategory('Foo', filter_fields=['a'], sort_by=sort_by,
                                  sort_order=sort_order)
    cat.set_pattern('')
    validate_model(cat, expected)


@pytest.mark.parametrize('pattern, filter_cols, before, after', [
    ('foo', [0],
     [('foo', '', ''), ('bar', '', ''), ('aafobbb', '', '')],
     [('foo',)]),

    ('foo', [0],
     [('baz', 'bar', 'foo'), ('foo', '', ''), ('bar', 'foo', '')],
     [('foo', '', '')]),

    ('foo', [0],
     [('fooa', '', ''), ('foob', '', ''), ('fooc', '', '')],
     [('fooa', '', ''), ('foob', '', ''), ('fooc', '', '')]),

    ('foo', [1],
     [('foo', 'bar', ''), ('bar', 'foo', '')],
     [('bar', 'foo', '')]),

    ('foo', [0, 1],
     [('foo', 'bar', ''), ('bar', 'foo', ''), ('biz', 'baz', 'foo')],
     [('foo', 'bar', ''), ('bar', 'foo', '')]),

    ('foo', [0, 1, 2],
     [('foo', '', ''), ('bar', '', ''), ('baz', 'bar', 'foo')],
     [('foo', '', ''), ('baz', 'bar', 'foo')]),

    ('foo bar', [0],
     [('foo', '', ''), ('bar foo', '', ''), ('xfooyybarz', '', '')],
     [('xfooyybarz', '', '')]),

    ('foo%bar', [0],
     [('foo%bar', '', ''), ('foo bar', '', ''), ('foobar', '', '')],
     [('foo%bar', '', '')]),

    ('_', [0],
     [('a_b', '', ''), ('__a', '', ''), ('abc', '', '')],
     [('a_b', '', ''), ('__a', '', '')]),

    ('%', [0, 1],
     [('\\foo', '\\bar', '')],
     []),

    ("can't", [0],
     [("can't touch this", '', ''), ('a', '', '')],
     [("can't touch this", '', '')]),
])
def test_set_pattern(pattern, filter_cols, before, after, validate_model):
    """Validate the filtering and sorting results of set_pattern."""
    table = sql.SqlTable('Foo', ['a', 'b', 'c'])
    for row in before:
        table.insert({'a': row[0], 'b': row[1], 'c': row[2]})
    filter_fields = [['a', 'b', 'c'][i] for i in filter_cols]
    cat = sqlcategory.SqlCategory('Foo', filter_fields=filter_fields)
    cat.set_pattern(pattern)
    validate_model(cat, after)


def test_select(validate_model):
    table = sql.SqlTable('Foo', ['a', 'b', 'c'])
    table.insert({'a': 'foo', 'b': 'bar', 'c': 'baz'})
    cat = sqlcategory.SqlCategory('Foo', filter_fields=['a'], select='b, c, a')
    cat.set_pattern('')
    validate_model(cat, [('bar', 'baz', 'foo')])


def test_delete_cur_item():
    table = sql.SqlTable('Foo', ['a', 'b'])
    table.insert({'a': 'foo', 'b': 1})
    table.insert({'a': 'bar', 'b': 2})
    func = unittest.mock.Mock(spec=[])
    cat = sqlcategory.SqlCategory('Foo', filter_fields=['a'], delete_func=func)
    cat.set_pattern('')
    cat.delete_cur_item(cat.index(0, 0))
    func.assert_called_with(['foo', 1])


def test_delete_cur_item_no_func():
    table = sql.SqlTable('Foo', ['a', 'b'])
    table.insert({'a': 'foo', 'b': 1})
    table.insert({'a': 'bar', 'b': 2})
    cat = sqlcategory.SqlCategory('Foo', filter_fields=['a'])
    cat.set_pattern('')
    with pytest.raises(cmdexc.CommandError, match='Cannot delete this item'):
        cat.delete_cur_item(cat.index(0, 0))
