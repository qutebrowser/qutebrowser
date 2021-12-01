# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2019-2021 Jay Kamat <jaygkamat@gmail.com>:
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for the BindingTrie."""

import string
import itertools
import textwrap

import pytest

from PyQt5.QtGui import QKeySequence

from qutebrowser.keyinput import basekeyparser
from qutebrowser.keyinput import keyutils
from unit.keyinput import test_keyutils


@pytest.mark.parametrize('entered, configured, match_type',
                         test_keyutils.TestKeySequence.MATCH_TESTS)
def test_matches_single(entered, configured, match_type):
    entered = keyutils.KeySequence.parse(entered)
    configured = keyutils.KeySequence.parse(configured)
    trie = basekeyparser.BindingTrie()
    trie[configured] = "eeloo"
    command = "eeloo" if match_type == QKeySequence.ExactMatch else None
    result = basekeyparser.MatchResult(match_type=match_type,
                                       command=command,
                                       sequence=entered)
    assert trie.matches(entered) == result


def test_str():
    bindings = {
        keyutils.KeySequence.parse('a'): 'cmd-a',
        keyutils.KeySequence.parse('ba'): 'cmd-ba',
        keyutils.KeySequence.parse('bb'): 'cmd-bb',
        keyutils.KeySequence.parse('cax'): 'cmd-cax',
        keyutils.KeySequence.parse('cby'): 'cmd-cby',
    }
    trie = basekeyparser.BindingTrie()
    trie.update(bindings)

    expected = """
        a:
          => cmd-a

        b:
          a:
            => cmd-ba
          b:
            => cmd-bb

        c:
          a:
            x:
              => cmd-cax
          b:
            y:
              => cmd-cby
    """

    assert str(trie) == textwrap.dedent(expected).lstrip('\n')


@pytest.mark.parametrize('configured, expected', [
    ([],
     # null match
     [('a', QKeySequence.NoMatch),
      ('', QKeySequence.NoMatch)]),
    (['abcd'],
     [('abcd', QKeySequence.ExactMatch),
      ('abc', QKeySequence.PartialMatch)]),
    (['aa', 'ab', 'ac', 'ad'],
     [('ac', QKeySequence.ExactMatch),
      ('a', QKeySequence.PartialMatch),
      ('f', QKeySequence.NoMatch),
      ('acd', QKeySequence.NoMatch)]),
    (['aaaaaaab', 'aaaaaaac', 'aaaaaaad'],
     [('aaaaaaab', QKeySequence.ExactMatch),
      ('z', QKeySequence.NoMatch)]),
    (string.ascii_letters,
     [('a', QKeySequence.ExactMatch),
      ('!', QKeySequence.NoMatch)]),
])
def test_matches_tree(configured, expected, benchmark):
    trie = basekeyparser.BindingTrie()
    trie.update({keyutils.KeySequence.parse(keys): "eeloo"
                 for keys in configured})

    def run():
        for entered, match_type in expected:
            sequence = keyutils.KeySequence.parse(entered)
            command = ("eeloo" if match_type == QKeySequence.ExactMatch
                       else None)
            result = basekeyparser.MatchResult(match_type=match_type,
                                               command=command,
                                               sequence=sequence)
            assert trie.matches(sequence) == result

    benchmark(run)


@pytest.mark.parametrize('configured', [
    ['a'],
    itertools.permutations('asdfghjkl', 3)
])
def test_bench_create(configured, benchmark):
    bindings = {keyutils.KeySequence.parse(keys): "dres"
                for keys in configured}

    def run():
        trie = basekeyparser.BindingTrie()
        trie.update(bindings)

    benchmark(run)
