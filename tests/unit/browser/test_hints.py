# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import string
import functools
import operator

import pytest

import qutebrowser.browser.hints


@pytest.mark.parametrize('min_len', [0, 3])
@pytest.mark.parametrize('num_chars', [9])
@pytest.mark.parametrize('num_elements', range(1, 26))
def test_scattered_hints_count(win_registry, mode_manager, min_len,
                               num_chars, num_elements):
    """Test scattered hints function.

    Tests many properties from an invocation of _hint_scattered, including

    1. Hints must be unique
    2. There can only be two hint lengths, only 1 apart
    3. There are no unique prefixes for long hints, such as 'la' with no 'l<x>'
    """
    manager = qutebrowser.browser.hints.HintManager(0, 0)
    chars = string.ascii_lowercase[:num_chars]

    hints = manager._hint_scattered(min_len, chars,
                                    list(range(num_elements)))

    # Check if hints are unique
    assert len(hints) == len(set(hints))

    # Check if any hints are shorter than min_len
    assert not any(x for x in hints if len(x) < min_len)

    # Check we don't have more than 2 link lengths
    # Eg: 'a' 'bc' and 'def' cannot be in the same hint string
    hint_lens = {len(h) for h in hints}
    assert len(hint_lens) <= 2

    if len(hint_lens) == 2:
        # Check if hint_lens are more than 1 apart
        # Eg: 'abc' and 'd' cannot be in the same hint sequence, but
        # 'ab' and 'c' can
        assert abs(functools.reduce(operator.sub, hint_lens)) <= 1

    longest_hints = [x for x in hints if len(x) == max(hint_lens)]

    if min_len < max(hint_lens) - 1:
        # Check if we have any unique prefixes. For example, 'la'
        # alone, with no other 'l<x>'
        count_map = {}
        for x in longest_hints:
            prefix = x[:-1]
            count_map[prefix] = count_map.get(prefix, 0) + 1
        assert all(e != 1 for e in count_map.values())
