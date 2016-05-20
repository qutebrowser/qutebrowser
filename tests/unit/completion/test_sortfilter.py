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

from qutebrowser.completion.models import base, sortfilter


@pytest.mark.parametrize('pattern, data, expected', [
    ('foo', 'barfoobar', True),
    ('foo', 'barFOObar', True),
    ('Foo', 'barfOObar', True),
    ('ab', 'aonebtwo', False),
    ('33', 'l33t', True),
    ('x', 'blah', False),
    ('4', 'blah', False),
])
def test_filter_accepts_row(pattern, data, expected):
    source_model = base.BaseCompletionModel()
    cat = source_model.new_category('test')
    source_model.new_item(cat, data)

    filter_model = sortfilter.CompletionFilterModel(source_model)
    filter_model.set_pattern(pattern)
    assert filter_model.rowCount() == 1  # "test" category
    idx = filter_model.index(0, 0)
    assert idx.isValid()

    row_count = filter_model.rowCount(idx)
    assert row_count == (1 if expected else 0)
