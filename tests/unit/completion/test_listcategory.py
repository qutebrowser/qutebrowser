# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from qutebrowser.completion.models import listcategory


def _validate(cat, expected):
    """Check that a category contains the expected items in the given order.

    Args:
        cat: The category to inspect.
        expected: A list of tuples containing the expected items.
    """
    assert cat.rowCount() == len(expected)
    for row, items in enumerate(expected):
        for col, item in enumerate(items):
            assert cat.data(cat.index(row, col)) == item


@pytest.mark.parametrize('pattern, filter_cols, before, after', [
    ('foo', [0],
     [('foo', '', ''), ('bar', '', '')],
     [('foo', '', '')]),

    ('foo', [0],
     [('foob', '', ''), ('fooc', '', ''), ('fooa', '', '')],
     [('fooa', '', ''), ('foob', '', ''), ('fooc', '', '')]),

    # prefer foobar as it starts with the pattern
    ('foo', [0],
     [('barfoo', '', ''), ('foobar', '', '')],
     [('foobar', '', ''), ('barfoo', '', '')]),

    ('foo', [1],
     [('foo', 'bar', ''), ('bar', 'foo', '')],
     [('bar', 'foo', '')]),

    ('foo', [0, 1],
     [('foo', 'bar', ''), ('bar', 'foo', ''), ('bar', 'bar', '')],
     [('foo', 'bar', ''), ('bar', 'foo', '')]),

    ('foo', [0, 1, 2],
     [('foo', '', ''), ('bar', '')],
     [('foo', '', '')]),
])
def test_set_pattern(pattern, filter_cols, before, after):
    """Validate the filtering and sorting results of set_pattern."""
    cat = listcategory.ListCategory('Foo', before,
                                    columns_to_filter=filter_cols)
    cat.set_pattern(pattern)
    _validate(cat, after)
