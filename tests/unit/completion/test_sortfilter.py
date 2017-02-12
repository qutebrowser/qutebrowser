# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for CompletionFilterModel."""

import pytest

from qutebrowser.completion.models import base, sortfilter


def _create_model(data):
    """Create a completion model populated with the given data.

    data: A list of lists, where each sub-list represents a category, each
          tuple in the sub-list represents an item, and each value in the
          tuple represents the item data for that column
    """
    model = base.CompletionModel()
    for catdata in data:
        cat = model.new_category('')
        for itemdata in catdata:
            model.new_item(cat, *itemdata)
    return model


def _extract_model_data(model):
    """Express a model's data as a list for easier comparison.

    Return: A list of lists, where each sub-list represents a category, each
            tuple in the sub-list represents an item, and each value in the
            tuple represents the item data for that column
    """
    data = []
    for i in range(0, model.rowCount()):
        cat_idx = model.index(i, 0)
        row = []
        for j in range(0, model.rowCount(cat_idx)):
            row.append((model.data(cat_idx.child(j, 0)),
                        model.data(cat_idx.child(j, 1)),
                        model.data(cat_idx.child(j, 2))))
        data.append(row)
    return data


@pytest.mark.parametrize('pattern, data, expected', [
    ('foo', 'barfoobar', True),
    ('foo bar', 'barfoobar', True),
    ('foo   bar', 'barfoobar', True),
    ('foo bar', 'barfoobazbar', True),
    ('foo   bar', 'barfoobazbar', True),
    ('foo', 'barFOObar', True),
    ('Foo', 'barfOObar', True),
    ('ab', 'aonebtwo', False),
    ('33', 'l33t', True),
    ('x', 'blah', False),
    ('4', 'blah', False),
])
def test_filter_accepts_row(pattern, data, expected):
    source_model = base.CompletionModel()
    cat = source_model.new_category('test')
    source_model.new_item(cat, data)

    filter_model = sortfilter.CompletionFilterModel(source_model)
    filter_model.set_pattern(pattern)
    assert filter_model.rowCount() == 1  # "test" category
    idx = filter_model.index(0, 0)
    assert idx.isValid()

    row_count = filter_model.rowCount(idx)
    assert row_count == (1 if expected else 0)


@pytest.mark.parametrize('tree, first, last', [
    ([[('Aa',)]], 'Aa', 'Aa'),
    ([[('Aa',)], [('Ba',)]], 'Aa', 'Ba'),
    ([[('Aa',), ('Ab',), ('Ac',)], [('Ba',), ('Bb',)], [('Ca',)]],
     'Aa', 'Ca'),
    ([[], [('Ba',)]], 'Ba', 'Ba'),
    ([[], [], [('Ca',)]], 'Ca', 'Ca'),
    ([[], [], [('Ca',), ('Cb',)]], 'Ca', 'Cb'),
    ([[('Aa',)], []], 'Aa', 'Aa'),
    ([[('Aa',)], []], 'Aa', 'Aa'),
    ([[('Aa',)], [], []], 'Aa', 'Aa'),
    ([[('Aa',)], [], [('Ca',)]], 'Aa', 'Ca'),
    ([[], []], None, None),
])
def test_first_last_item(tree, first, last):
    """Test that first() and last() return indexes to the first and last items.

    Args:
        tree: Each list represents a completion category, with each string
              being an item under that category.
        first: text of the first item
        last: text of the last item
    """
    model = _create_model(tree)
    filter_model = sortfilter.CompletionFilterModel(model)
    assert filter_model.data(filter_model.first_item()) == first
    assert filter_model.data(filter_model.last_item()) == last


def test_set_source_model():
    """Ensure setSourceModel sets source_model and clears the pattern."""
    model1 = base.CompletionModel()
    model2 = base.CompletionModel()
    filter_model = sortfilter.CompletionFilterModel(model1)
    filter_model.set_pattern('foo')
    # sourceModel() is cached as srcmodel, so make sure both match
    assert filter_model.srcmodel is model1
    assert filter_model.sourceModel() is model1
    assert filter_model.pattern == 'foo'
    filter_model.setSourceModel(model2)
    assert filter_model.srcmodel is model2
    assert filter_model.sourceModel() is model2
    assert not filter_model.pattern


@pytest.mark.parametrize('tree, expected', [
    ([[('Aa',)]], 1),
    ([[('Aa',)], [('Ba',)]], 2),
    ([[('Aa',), ('Ab',), ('Ac',)], [('Ba',), ('Bb',)], [('Ca',)]], 6),
    ([[], [('Ba',)]], 1),
    ([[], [], [('Ca',)]], 1),
    ([[], [], [('Ca',), ('Cb',)]], 2),
    ([[('Aa',)], []], 1),
    ([[('Aa',)], []], 1),
    ([[('Aa',)], [], []], 1),
    ([[('Aa',)], [], [('Ca',)]], 2),
])
def test_count(tree, expected):
    model = _create_model(tree)
    filter_model = sortfilter.CompletionFilterModel(model)
    assert filter_model.count() == expected


@pytest.mark.parametrize('pattern, filter_cols, before, after', [
    ('foo', [0],
     [[('foo', '', ''), ('bar', '', '')]],
     [[('foo', '', '')]]),

    ('foo', [0],
     [[('foob', '', ''), ('fooc', '', ''), ('fooa', '', '')]],
     [[('fooa', '', ''), ('foob', '', ''), ('fooc', '', '')]]),

    ('foo', [0],
     [[('foo', '', '')], [('bar', '', '')]],
     [[('foo', '', '')], []]),

    # prefer foobar as it starts with the pattern
    ('foo', [0],
     [[('barfoo', '', ''), ('foobar', '', '')]],
     [[('foobar', '', ''), ('barfoo', '', '')]]),

    # however, don't rearrange categories
    ('foo', [0],
     [[('barfoo', '', '')], [('foobar', '', '')]],
     [[('barfoo', '', '')], [('foobar', '', '')]]),

    ('foo', [1],
     [[('foo', 'bar', ''), ('bar', 'foo', '')]],
     [[('bar', 'foo', '')]]),

    ('foo', [0, 1],
     [[('foo', 'bar', ''), ('bar', 'foo', ''), ('bar', 'bar', '')]],
     [[('foo', 'bar', ''), ('bar', 'foo', '')]]),

    ('foo', [0, 1, 2],
     [[('foo', '', ''), ('bar', '')]],
     [[('foo', '', '')]]),
])
def test_set_pattern(pattern, filter_cols, before, after):
    """Validate the filtering and sorting results of set_pattern."""
    model = _create_model(before)
    model.columns_to_filter = filter_cols
    filter_model = sortfilter.CompletionFilterModel(model)
    filter_model.set_pattern(pattern)
    actual = _extract_model_data(filter_model)
    assert actual == after
