# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019 Jay Kamat <jaygkamat@gmail.com>:
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

"""Tests for the BindingTrie."""

import string
import itertools

import pytest

from PyQt5.QtGui import QKeySequence

from qutebrowser.keyinput import basekeyparser
from qutebrowser.keyinput import keyutils
from unit.keyinput import test_keyutils


@pytest.mark.parametrize('entered, configured, expected',
                         test_keyutils.TestKeySequence.MATCH_TESTS)
def test_matches_single(entered, configured, expected):
    entered = keyutils.KeySequence.parse(entered)
    configured = keyutils.KeySequence.parse(configured)
    trie = basekeyparser.BindingTrie()
    trie[configured] = "eeloo"
    ret_expected = None
    if expected == QKeySequence.ExactMatch:
        ret_expected = "eeloo"
    assert trie.matches(entered) == (expected, ret_expected)


@pytest.mark.parametrize(
    'configured, expected_tuple',
    (((),
      # null match
      (('a', QKeySequence.NoMatch),
       ('', QKeySequence.NoMatch))),
     (('abcd',),
      (('abcd', QKeySequence.ExactMatch),
       ('abc', QKeySequence.PartialMatch))),
     (('aa', 'ab', 'ac', 'ad'),
      (('ac', QKeySequence.ExactMatch),
       ('a', QKeySequence.PartialMatch),
       ('f', QKeySequence.NoMatch),
       ('acd', QKeySequence.NoMatch))),
     (('aaaaaaab', 'aaaaaaac', 'aaaaaaad'),
      (('aaaaaaab', QKeySequence.ExactMatch),
       ('z', QKeySequence.NoMatch))),
     (tuple(string.ascii_letters),
      (('a', QKeySequence.ExactMatch),
       ('!', QKeySequence.NoMatch)))))
def test_matches_tree(configured, expected_tuple, benchmark):
    trie = basekeyparser.BindingTrie()
    trie.update(dict.fromkeys(
        map(keyutils.KeySequence.parse, configured), "eeloo"))

    def _run():
        for entered, expected in expected_tuple:
            entered = keyutils.KeySequence.parse(entered)
            ret_expected = None
            if expected == QKeySequence.ExactMatch:
                ret_expected = "eeloo"
            assert trie.matches(entered) == (expected, ret_expected)
    benchmark(_run)


@pytest.mark.parametrize(
    'configured',
    ('a',
     itertools.permutations('asdfghjkl', 3)))
def test_bench_create(configured, benchmark):
    configured = dict.fromkeys(
        map(keyutils.KeySequence.parse, configured), "dres")

    def _run():
        trie = basekeyparser.BindingTrie()
        trie.update(configured)
    benchmark(_run)
