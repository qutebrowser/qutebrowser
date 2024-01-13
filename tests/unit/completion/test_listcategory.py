# SPDX-FileCopyrightText: Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for CompletionFilterModel."""

import logging

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

    ('foo bar',
     [('foobar', ''), ('barfoo', ''), ('foobaz', '')],
     [('barfoo', ''), ('foobar', '')],
     [('foobar', ''), ('barfoo', '')]),
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


def test_long_pattern(caplog, model_validator):
    """Validate that a huge pattern doesn't crash (#5973)."""
    with caplog.at_level(logging.WARNING):
        cat = listcategory.ListCategory('Foo', [('a' * 5000, '')])
        model_validator.set_model(cat)
        cat.set_pattern('a' * 50000)
        model_validator.validate([('a' * 5000, '')])
