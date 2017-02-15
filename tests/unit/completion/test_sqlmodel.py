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

"""Tests for the base sql completion model."""

import pytest
from PyQt5.QtCore import Qt

from qutebrowser.misc import sql
from qutebrowser.completion.models import sqlmodel


pytestmark = pytest.mark.usefixtures('init_sql')


def _check_model(model, expected):
    """Check that a model contains the expected items in the given order.

    Args:
        expected: A list of form
                  [
                      (cat, [(name, desc, misc), (name, desc, misc), ...]),
                      (cat, [(name, desc, misc), (name, desc, misc), ...]),
                      ...
                  ]
    """
    assert model.rowCount() == len(expected)
    for i, (expected_title, expected_items) in enumerate(expected):
        catidx = model.index(i, 0)
        assert model.data(catidx) == expected_title
        assert model.rowCount(catidx) == len(expected_items)
        for j, (name, desc, misc) in enumerate(expected_items):
            assert model.data(model.index(j, 0, catidx)) == name
            assert model.data(model.index(j, 1, catidx)) == desc
            assert model.data(model.index(j, 2, catidx)) == misc


@pytest.mark.parametrize('rowcounts, expected', [
    ([0], 0),
    ([1], 1),
    ([2], 2),
    ([0, 0], 0),
    ([0, 0, 0], 0),
    ([1, 1], 2),
    ([3, 2, 1], 6),
    ([0, 2, 0], 2),
])
def test_count(rowcounts, expected):
    model = sqlmodel.SqlCompletionModel()
    for i, rowcount in enumerate(rowcounts):
        name = 'Foo' + str(i)
        table = sql.SqlTable(name, ['a'], primary_key='a')
        for rownum in range(rowcount):
            table.insert([rownum])
        model.new_category(name)
    assert model.count() == expected


@pytest.mark.parametrize('sort_by, sort_order, data, expected', [
    (None, Qt.AscendingOrder,
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')]),

    ('a', Qt.AscendingOrder,
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('A', 'F', 'C'), ('B', 'C', 'D'), ('C', 'A', 'G')]),

    ('a', Qt.DescendingOrder,
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('C', 'A', 'G'), ('B', 'C', 'D'), ('A', 'F', 'C')]),

    ('b', Qt.AscendingOrder,
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('C', 'A', 'G'), ('B', 'C', 'D'), ('A', 'F', 'C')]),

    ('b', Qt.DescendingOrder,
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('A', 'F', 'C'), ('B', 'C', 'D'), ('C', 'A', 'G')]),

    ('c', Qt.AscendingOrder,
     [('B', 'C', 2), ('A', 'F', 0), ('C', 'A', 1)],
     [('A', 'F', 0), ('C', 'A', 1), ('B', 'C', 2)]),

    ('c', Qt.DescendingOrder,
     [('B', 'C', 2), ('A', 'F', 0), ('C', 'A', 1)],
     [('B', 'C', 2), ('C', 'A', 1), ('A', 'F', 0)]),
])
def test_sorting(sort_by, sort_order, data, expected):
    table = sql.SqlTable('Foo', ['a', 'b', 'c'], primary_key='a')
    for row in data:
        table.insert(row)
    model = sqlmodel.SqlCompletionModel()
    model.new_category('Foo', sort_by=sort_by, sort_order=sort_order)
    _check_model(model, [('Foo', expected)])


@pytest.mark.parametrize('pattern, filter_cols, before, after', [
    ('foo', [0],
     [('A', [('foo', '', ''), ('bar', '', ''), ('aafobbb', '', '')])],
     [('A', [('foo', '', '')])]),

    ('foo', [0],
     [('A', [('baz', 'bar', 'foo'), ('foo', '', ''), ('bar', 'foo', '')])],
     [('A', [('foo', '', '')])]),

    ('foo', [0],
     [('A', [('foo', '', ''), ('bar', '', '')]),
      ('B', [('foo', '', ''), ('bar', '', '')])],
     [('A', [('foo', '', '')]), ('B', [('foo', '', '')])]),

    ('foo', [0],
     [('A', [('fooa', '', ''), ('foob', '', ''), ('fooc', '', '')])],
     [('A', [('fooa', '', ''), ('foob', '', ''), ('fooc', '', '')])]),

    ('foo', [0],
     [('A', [('foo', '', '')]), ('B', [('bar', '', '')])],
     [('A', [('foo', '', '')]), ('B', [])]),

    ('foo', [1],
     [('A', [('foo', 'bar', ''), ('bar', 'foo', '')])],
     [('A', [('bar', 'foo', '')])]),

    ('foo', [0, 1],
     [('A', [('foo', 'bar', ''), ('bar', 'foo', '')])],
     [('A', [('foo', 'bar', ''), ('bar', 'foo', '')])]),

    ('foo', [0, 1, 2],
     [('A', [('foo', '', ''), ('bar', '', '')])],
     [('A', [('foo', '', '')])]),

    ('foo bar', [0],
     [('A', [('foo', '', ''), ('bar foo', '', ''), ('xfooyybarz', '', '')])],
     [('A', [('xfooyybarz', '', '')])]),

    ('foo%bar', [0],
     [('A', [('foo%bar', '', ''), ('foo bar', '', ''), ('foobar', '', '')])],
     [('A', [('foo%bar', '', '')])]),

    ('_', [0],
     [('A', [('a_b', '', ''), ('__a', '', ''), ('abc', '', '')])],
     [('A', [('a_b', '', ''), ('__a', '', '')])]),

    ('%', [0, 1],
     [('A', [('\\foo', '\\bar', '')])],
     [('A', [])]),

    ("can't", [0],
     [('A', [("can't touch this", '', ''), ('a', '', '')])],
     [('A', [("can't touch this", '', '')])]),
])
def test_set_pattern(pattern, filter_cols, before, after):
    """Validate the filtering and sorting results of set_pattern."""
    model = sqlmodel.SqlCompletionModel(columns_to_filter=filter_cols)
    for name, rows in before:
        table = sql.SqlTable(name, ['a', 'b', 'c'], primary_key='a')
        for row in rows:
            table.insert(row)
        model.new_category(name)
    model.set_pattern(pattern)
    _check_model(model, after)


@pytest.mark.parametrize('data, first, last', [
    ([('A', ['Aa'])], 'Aa', 'Aa'),
    ([('A', ['Aa', 'Ba'])], 'Aa', 'Ba'),
    ([('A', ['Aa', 'Ab', 'Ac']), ('B', ['Ba', 'Bb']),
        ('C', ['Ca'])], 'Aa', 'Ca'),
    ([('A', []), ('B', ['Ba'])], 'Ba', 'Ba'),
    ([('A', []), ('B', []), ('C', ['Ca'])], 'Ca', 'Ca'),
    ([('A', []), ('B', []), ('C', ['Ca', 'Cb'])], 'Ca', 'Cb'),
    ([('A', ['Aa']), ('B', [])], 'Aa', 'Aa'),
    ([('A', ['Aa']), ('B', []), ('C', [])], 'Aa', 'Aa'),
    ([('A', ['Aa']), ('B', []), ('C', ['Ca'])], 'Aa', 'Ca'),
    ([('A', []), ('B', [])], None, None),
])
def test_first_last_item(data, first, last):
    """Test that first() and last() return indexes to the first and last items.

    Args:
        data: Input to _make_model
        first: text of the first item
        last: text of the last item
    """
    model = sqlmodel.SqlCompletionModel()
    for name, rows in data:
        table = sql.SqlTable(name, ['a'], primary_key='a')
        for row in rows:
            table.insert([row])
        model.new_category(name)
    assert model.data(model.first_item()) == first
    assert model.data(model.last_item()) == last


def test_limit():
    table = sql.SqlTable('test_limit', ['a'], primary_key='a')
    for i in range(5):
        table.insert([i])
    model = sqlmodel.SqlCompletionModel()
    model.new_category('test_limit', limit=3)
    assert model.count() == 3


def test_select():
    table = sql.SqlTable('test_select', ['a', 'b', 'c'], primary_key='a')
    table.insert(['foo', 'bar', 'baz'])
    model = sqlmodel.SqlCompletionModel()
    model.new_category('test_select', select='b, c, a')
    _check_model(model, [('test_select', [('bar', 'baz', 'foo')])])


def test_where():
    table = sql.SqlTable('test_where', ['a', 'b', 'c'], primary_key='a')
    table.insert(['foo', 'bar', False])
    table.insert(['baz', 'biz', True])
    model = sqlmodel.SqlCompletionModel()
    model.new_category('test_where', where='not c')
    _check_model(model, [('test_where', [('foo', 'bar', False)])])


def test_entry():
    table = sql.SqlTable('test_entry', ['a', 'b', 'c'], primary_key='a')
    assert hasattr(table.Entry, 'a')
    assert hasattr(table.Entry, 'b')
    assert hasattr(table.Entry, 'c')
