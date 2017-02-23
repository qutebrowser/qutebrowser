# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""Tests for CompletionModel."""

import pytest

from qutebrowser.completion.models import completionmodel, sortfilter


def _create_model(data, filter_cols=None):
    """Create a completion model populated with the given data.

    data: A list of lists, where each sub-list represents a category, each
          tuple in the sub-list represents an item, and each value in the
          tuple represents the item data for that column
    filter_cols: Columns to filter, or None for default.
    """
    model = completionmodel.CompletionModel(columns_to_filter=filter_cols)
    for catdata in data:
        model.add_list('', catdata)
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
    assert model.data(model.first_item()) == first
    assert model.data(model.last_item()) == last


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
    assert model.count() == expected


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
    # TODO: just test that it calls the mock on its child categories
    model = _create_model(before, filter_cols)
    model.set_pattern(pattern)
    actual = _extract_model_data(model)
    assert actual == after
