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

from helpers import utils
from qutebrowser.completion.models import listcategory


@pytest.mark.parametrize('pattern, before, after', [
    ('foo',
     [('foo', ''), ('bar', '')],
     [('foo', '')]),

    ('foo',
     [('foob', ''), ('fooc', ''), ('fooa', '')],
     [('fooa', ''), ('foob', ''), ('fooc', '')]),

    # prefer foobar as it starts with the pattern
    ('foo',
     [('barfoo', ''), ('foobar', '')],
     [('foobar', ''), ('barfoo', '')]),

    ('foo',
     [('foo', 'bar'), ('bar', 'foo'), ('bar', 'bar')],
     [('foo', 'bar'), ('bar', 'foo')]),
])
def test_set_pattern(pattern, before, after):
    """Validate the filtering and sorting results of set_pattern."""
    cat = listcategory.ListCategory('Foo', before)
    cat.set_pattern(pattern)
    utils.validate_model(cat, after)
