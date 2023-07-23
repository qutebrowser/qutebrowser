# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from helpers import testutils

from qutebrowser.qt.widgets import QFrame


@pytest.mark.parametrize('val1, val2', [
    ({'a': 1}, {'a': 1}),
    ({'a': 1, 'b': 2}, {'a': 1}),
    ({'a': [1, 2, 3]}, {'a': [1]}),
    ({'a': [1, 2, 3]}, {'a': [..., 2]}),
    (1.0, 1.00000001),
    ("foobarbaz", "foo*baz"),
])
def test_partial_compare_equal(val1, val2):
    assert testutils.partial_compare(val1, val2)


@pytest.mark.parametrize('val1, val2, error', [
    ({'a': 1}, {'a': 2}, "1 != 2"),
    ({'a': 1}, {'b': 1}, "Key 'b' is in second dict but not in first!"),
    ({'a': 1, 'b': 2}, {'a': 2}, "1 != 2"),
    ({'a': [1]}, {'a': [1, 2, 3]}, "Second list is longer than first list"),
    ({'a': [1]}, {'a': [2, 3, 4]}, "Second list is longer than first list"),
    ([1], {1: 2}, "Different types (list, dict) -> False"),
    ({1: 1}, {1: [1]}, "Different types (int, list) -> False"),
    ({'a': [1, 2, 3]}, {'a': [..., 3]}, "2 != 3"),
    ("foo*baz", "foobarbaz", "'foo*baz' != 'foobarbaz' (pattern matching)"),
    (23.42, 13.37, "23.42 != 13.37 (float comparison)"),
])
def test_partial_compare_not_equal(val1, val2, error):
    outcome = testutils.partial_compare(val1, val2)
    assert not outcome
    assert isinstance(outcome, testutils.PartialCompareOutcome)
    assert outcome.error == error


@pytest.mark.parametrize('pattern, value, expected', [
    ('foo', 'foo', True),
    ('foo', 'bar', False),
    ('foo', 'Foo', False),
    ('foo', 'foobar', False),
    ('foo', 'barfoo', False),

    ('foo*', 'foobarbaz', True),
    ('*bar', 'foobar', True),
    ('foo*baz', 'foobarbaz', True),

    ('foo[b]ar', 'foobar', False),
    ('foo[b]ar', 'foo[b]ar', True),

    ('foo?ar', 'foobar', False),
    ('foo?ar', 'foo?ar', True),
])
def test_pattern_match(pattern, value, expected):
    assert testutils.pattern_match(pattern=pattern, value=value) == expected


def test_nop_contextmanager():
    with testutils.nop_contextmanager():
        pass


def test_enum_members():
    expected = {
        "Plain": QFrame.Shadow.Plain,
        "Raised": QFrame.Shadow.Raised,
        "Sunken": QFrame.Shadow.Sunken,
    }
    assert testutils.enum_members(QFrame, QFrame.Shadow) == expected
