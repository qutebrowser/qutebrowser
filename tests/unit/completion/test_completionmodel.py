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

import sys
import pytest
import hypothesis
from unittest import mock
from hypothesis import strategies

from qutebrowser.completion.models import completionmodel


@hypothesis.given(strategies.lists(min_size=0, max_size=3,
    elements=strategies.integers(min_value=0, max_value=2**31)))
def test_first_last_item(counts):
    """Test that first() and last() index to the first and last items."""
    model = completionmodel.CompletionModel()
    for c in counts:
        cat = mock.Mock()
        cat.rowCount = mock.Mock(return_value=c)
        model.add_category(cat)
    nonempty = [i for i, rowCount in enumerate(counts) if rowCount > 0]
    if not nonempty:
        # with no items, first and last should be an invalid index
        assert not model.first_item().isValid()
        assert not model.last_item().isValid()
    else:
        first = nonempty[0]
        last = nonempty[-1]
        # first item of the first nonempty category
        assert model.first_item().row() == 0
        assert model.first_item().parent().row() == first
        # last item of the last nonempty category
        assert model.last_item().row() == counts[last] - 1
        assert model.last_item().parent().row() == last


@hypothesis.given(strategies.lists(elements=strategies.integers(),
                                   min_size=0, max_size=3))
def test_count(counts):
    model = completionmodel.CompletionModel()
    for c in counts:
        cat = mock.Mock(spec=['rowCount'])
        cat.rowCount = mock.Mock(return_value=c)
        model.add_category(cat)
    assert model.count() == sum(counts)


@hypothesis.given(strategies.text())
def test_set_pattern(pat):
    """Validate the filtering and sorting results of set_pattern."""
    cols = [1, 2, 3]
    model = completionmodel.CompletionModel(columns_to_filter=cols)
    cats = [mock.Mock(spec=['set_pattern'])] * 3
    for c in cats:
        c.set_pattern = mock.Mock()
        model.add_category(c)
    model.set_pattern(pat)
    assert all(c.set_pattern.called_with([pat, cols]) for c in cats)
