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


@pytest.mark.parametrize('match_type, pattern, data, expected', [
    ('contain', 'foo', 'barfoobar', True),
    ('contain', 'foo', 'barFOObar', True),
    ('contain', 'Foo', 'barfOObar', True),
    ('contain', 'ab', 'aonebtwo', False),
    ('contain', '33', 'l33t', True),
    ('contain', 'x', 'blah', False),
    ('contain', '4', 'blah', False),

    ('fuzzy', 'foo', 'barfoobar', True),
    ('fuzzy', 'foo', 'barFoObar', True),
    ('fuzzy', 'fOO', 'barFoobar', True),
    ('fuzzy', 'ab', 'aonebtwo', True),
    ('fuzzy', 'abb', 'aonebtwo', True),
    ('fuzzy', 'abb', 'aonebtwob', True),
    ('fuzzy', 'abeb', 'aonebtwo', False),
    ('fuzzy', 'dore', 'download-remove', True),
    ('fuzzy', 'dorn', 'download-remove', False),
    ('fuzzy', 'x', 'blah', False),
    ('fuzzy', '14', 'bar1234Foobar', True),
    ('fuzzy', '14', 'bar3Foobar', False),
    ('fuzzy', 'ab', 'boneatwo', False),
    ('fuzzy', '/?', 'http://00hta.com', False),

    ('start', 'foo', 'foobar', True),
    ('start', '1oo', '1oobar', True),
    ('start', '1oo', '2arfoobar', False),
    ('start', 'foo', 'Foobar', True),
    ('start', 'Foo', 'foobar', True),
    ('start', 'foo', 'barfoobar', False),
    ('start', 'foo', 'barfoo', False),
    ('start', 'ab', 'aonebtwo', False),
    ('start', 'x', 'blah', False),
    ('start', 'ht', 'http://a.com', False),
    ('start', 'ht', 'http://aht.com', False),
    ('start', '11', 'http://aht.com', False),
    ('start', 'ht', 'http://hta.com', True),
    ('start', '00', 'http://00hta.com', True),
])
def test_filter_accepts_row(config_stub, match_type, pattern, data, expected):
    config_stub.data = {'completion': {'match-type': match_type}}

    source_model = base.BaseCompletionModel()
    cat = source_model.new_category('test')
    source_model.new_item(cat, data)

    filter_model = sortfilter.CompletionFilterModel(source_model)
    filter_model.set_pattern(pattern)
    assert filter_model.rowCount() == 1  # "test" category
    idx = filter_model.index(0, 0)
    assert idx.isValid()

    if expected:
        assert filter_model.rowCount(idx) == 1
    else:
        assert filter_model.rowCount(idx) == 0
