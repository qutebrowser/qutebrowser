# SPDX-FileCopyrightText: Jay Kamat <jaygkamat@gmail.com>:
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the BindingTrie."""

import string
import itertools
import textwrap

import pytest

from qutebrowser.qt.gui import QKeySequence

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
    command = "eeloo" if match_type == QKeySequence.SequenceMatch.ExactMatch else None
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
     [('a', QKeySequence.SequenceMatch.NoMatch),
      ('', QKeySequence.SequenceMatch.NoMatch)]),
    (['abcd'],
     [('abcd', QKeySequence.SequenceMatch.ExactMatch),
      ('abc', QKeySequence.SequenceMatch.PartialMatch)]),
    (['aa', 'ab', 'ac', 'ad'],
     [('ac', QKeySequence.SequenceMatch.ExactMatch),
      ('a', QKeySequence.SequenceMatch.PartialMatch),
      ('f', QKeySequence.SequenceMatch.NoMatch),
      ('acd', QKeySequence.SequenceMatch.NoMatch)]),
    (['aaaaaaab', 'aaaaaaac', 'aaaaaaad'],
     [('aaaaaaab', QKeySequence.SequenceMatch.ExactMatch),
      ('z', QKeySequence.SequenceMatch.NoMatch)]),
    (string.ascii_letters,
     [('a', QKeySequence.SequenceMatch.ExactMatch),
      ('!', QKeySequence.SequenceMatch.NoMatch)]),
])
def test_matches_tree(configured, expected, benchmark):
    trie = basekeyparser.BindingTrie()
    trie.update({keyutils.KeySequence.parse(keys): "eeloo"
                 for keys in configured})

    def run():
        for entered, match_type in expected:
            sequence = keyutils.KeySequence.parse(entered)
            command = ("eeloo" if match_type == QKeySequence.SequenceMatch.ExactMatch
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
