# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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


@pytest.mark.parametrize('pattern, before, after, after_nosort', [
    ('foo',
     [('foo', ''), ('bar', '')],
     [('foo', '')],
     [('foo', '')]),

    ('foo',
     [('foob', ''), ('fooc', ''), ('fooa', '')],
     [('fooa', ''), ('foob', ''), ('fooc', '')],
     [('foob', ''), ('fooc', ''), ('fooa', '')]),

    # prefer foobar as it starts with the pattern
    ('foo',
     [('barfoo', ''), ('foobaz', ''), ('foobar', '')],
     [('foobar', ''), ('foobaz', ''), ('barfoo', '')],
     [('foobaz', ''), ('foobar', ''), ('barfoo', '')]),

    ('foo',
     [('foo', 'bar'), ('bar', 'foo'), ('bar', 'bar')],
     [('foo', 'bar'), ('bar', 'foo')],
     [('foo', 'bar'), ('bar', 'foo')]),
])
def test_set_pattern(pattern, before, after, after_nosort, model_validator):
    """Validate the filtering and sorting results of set_pattern."""
    cat = listcategory.ListCategory('Foo', before)
    model_validator.set_model(cat)
    cat.set_pattern(pattern)
    model_validator.validate(after)

    cat = listcategory.ListCategory('Foo', before, sort=False)
    model_validator.set_model(cat)
    cat.set_pattern(pattern)
    model_validator.validate(after_nosort)
