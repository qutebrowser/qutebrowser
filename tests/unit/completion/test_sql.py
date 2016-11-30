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

from qutebrowser.completion.models import sql


def _make_model(data):
    """Create a completion model populated with the given data.

    Args:
        data: A list of form
              [
                  (cat, [(name, desc, misc), (name, desc, misc), ...]),
                  (cat, [(name, desc, misc), (name, desc, misc), ...]),
                  ...
              ]
    Returns: (model, categories)
    """
    model = sql.SqlCompletionModel()
    categories = []
    for title, children in data:
        categories.append(_add_category(model, title, children))
    return model, categories


def _add_category(model, name, items, **kwargs):
    """Add a new category to the model with children.

    Args:
        model: The model to add the category to.
        name: The title of the category.
        items: A list of tuples containing column data for each entry.
        kwargs: Keyword arguments passed through to model.new_category.
    """
    cat = model.new_category(name, **kwargs)
    for item in items:
        cat.new_item(*item)
    return cat


def _check_model(model, expected):
    """Check that a model contains the expected items in any order.

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


@pytest.fixture(autouse=True)
def init():
    sql.init()
    yield
    sql.close()


def test_new_item(qtmodeltester):
    """Test adding items to a SqlCompletionModel."""
    model, _ = _make_model([
        ("CatZero", [
            ('one', 'The first number', 'I'),
            ('two', 'Comes after one', 'II'),
            ('three', 'Even bigger than two', 'III'),
        ]),
        ("CatOne", [
            ('four', 'twice two', ''),
            ('five', 'twice two plus one', ''),
        ]),
        ("CatTwo", [])
    ])

    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)
    _check_model(model, [
        ("CatZero", [
            ('one', 'The first number', 'I'),
            ('two', 'Comes after one', 'II'),
            ('three', 'Even bigger than two', 'III'),
        ]),
        ("CatOne", [
            ('four', 'twice two', ''),
            ('five', 'twice two plus one', ''),
        ]),
        ("CatTwo", [])
    ])


def test_new_item_duplicate(qtmodeltester):
    """Ensure that adding a duplicate item fails."""
    model = sql.SqlCompletionModel()
    cat = model.new_category('Foo')
    cat.new_item('foo')
    with pytest.raises(sql.SqlException):
        cat.new_item('foo')


def test_remove_item(qtmodeltester):
    """Test removing items from a SqlCompletionModel."""
    model = sql.SqlCompletionModel()

    cat0 = model.new_category('A')
    cat0.new_item('one', 'The first number', 'I')
    cat0.new_item('two', 'Comes after one', 'II')
    cat0.new_item('three', 'Even bigger than two', 'III')

    cat1 = model.new_category('B', primary_key='desc')
    cat1.new_item('four', 'twice two', 'IV')
    cat1.new_item('five', 'twice two plus one', 'V')

    cat2 = model.new_category('C', primary_key='misc')
    cat2.new_item('six', 'twice three', 'VI')

    cat0.remove_item('two')
    cat1.remove_item('twice two')
    cat1.remove_item('twice two plus one')
    cat2.remove_item('VI')
    qtmodeltester.data_display_may_return_none = True
    qtmodeltester.check(model)
    _check_model(model, [
        ('A', [
            ('one', 'The first number', 'I'),
            ('three', 'Even bigger than two', 'III'),
        ]),
        ('B', []),
        ('C', [])
    ])


@pytest.mark.parametrize('data, expected', [
    ([('A', [(0,)])], 1),
    ([('A', [(0,)]), ('B', [(0,)])], 2),
    ([('A', [(0,), (1,), (2,)]), ('B', [(0,), (1,)]), ('C', [(0,)])], 6),
    ([('A', []), ('B', [(0,)])], 1),
    ([('A', []), ('B', []), ('C', [(0,)])], 1),
    ([('A', []), ('B', []), ('C', [(0,), (1,)])], 2),
    ([('A', [(0,)]), ('B', [])], 1),
    ([('A', [(0,)]), ('B', []), ('C', [])], 1),
    ([('A', [(0,)]), ('B', []), ('C', [(0,)])], 2),
])
def test_count(data, expected):
    model, _ = _make_model(data)
    assert model.count() == expected


@pytest.mark.parametrize('sort_by, sort_order, data, expected', [
    (None, Qt.AscendingOrder,
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')]),

    ('name', Qt.AscendingOrder,
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('A', 'F', 'C'), ('B', 'C', 'D'), ('C', 'A', 'G')]),

    ('name', Qt.DescendingOrder,
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('C', 'A', 'G'), ('B', 'C', 'D'), ('A', 'F', 'C')]),

    ('desc', Qt.AscendingOrder,
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('C', 'A', 'G'), ('B', 'C', 'D'), ('A', 'F', 'C')]),

    ('desc', Qt.DescendingOrder,
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('A', 'F', 'C'), ('B', 'C', 'D'), ('C', 'A', 'G')]),

    ('misc', Qt.AscendingOrder,
     [('B', 'C', 'D'), ('A', 'F', 'C'), ('C', 'A', 'G')],
     [('A', 'F', 'C'), ('B', 'C', 'D'), ('C', 'A', 'G')]),

    ('sort', Qt.AscendingOrder,
     [('B', 'C', 'D', 2), ('A', 'F', 'C', 3), ('C', 'A', 'G', 1)],
     [('C', 'A', 'G'), ('B', 'C', 'D'), ('A', 'F', 'C')]),
])
def test_sorting(sort_by, sort_order, data, expected):
    print("sort_by = {}".format(sort_by))
    model = sql.SqlCompletionModel()
    _add_category(model, 'Foo', data, sort_by=sort_by, sort_order=sort_order)
    expected = [('Foo', expected)]
    _check_model(model, expected)


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
     [('A', [('foo', '', ''), ('bar', '')])],
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
])
def test_set_pattern(pattern, filter_cols, before, after):
    """Validate the filtering and sorting results of set_pattern."""
    model, _ = _make_model(before)
    model.columns_to_filter = filter_cols
    model.set_pattern(pattern)
    _check_model(model, after)


@pytest.mark.parametrize('data, first, last', [
    ([('A', [('Aa',)])], 'Aa', 'Aa'),
    ([('A', [('Aa',), ('Ba',)])], 'Aa', 'Ba'),
    ([('A', [('Aa',), ('Ab',), ('Ac',)]), ('B', [('Ba',), ('Bb',)]),
        ('C', [('Ca',)])], 'Aa', 'Ca'),
    ([('A', []), ('B', [('Ba',)])], 'Ba', 'Ba'),
    ([('A', []), ('B', []), ('C', [('Ca',)])], 'Ca', 'Ca'),
    ([('A', []), ('B', []), ('C', [('Ca',), ('Cb',)])], 'Ca', 'Cb'),
    ([('A', [('Aa',)]), ('B', [])], 'Aa', 'Aa'),
    ([('A', [('Aa',)]), ('B', []), ('C', [])], 'Aa', 'Aa'),
    ([('A', [('Aa',)]), ('B', []), ('C', [('Ca',)])], 'Aa', 'Ca'),
    ([('A', []), ('B', [])], None, None),
])
def test_first_last_item(data, first, last):
    """Test that first() and last() return indexes to the first and last items.

    Args:
        data: Input to _make_model
        first: text of the first item
        last: text of the last item
    """
    model, _ = _make_model(data)
    assert model.data(model.first_item()) == first
    assert model.data(model.last_item()) == last
