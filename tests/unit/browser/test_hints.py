# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import itertools
import operator

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.utils import usertypes
import qutebrowser.browser.hints


@pytest.fixture(autouse=True)
def setup(benchmark, win_registry, mode_manager):
    yield
    # WORKAROUND for https://github.com/ionelmc/pytest-benchmark/issues/125
    benchmark._mode = 'WORKAROUND'  # pylint: disable=protected-access


@pytest.fixture
def tabbed_browser(tabbed_browser_stubs, web_tab):
    tb = tabbed_browser_stubs[0]
    tb.widget.tabs = [web_tab]
    tb.widget.current_index = 1
    tb.widget.cur_url = QUrl('https://www.example.com/')
    web_tab.container.expose()  # No elements found if we don't do this.
    return tb


def test_show_benchmark(benchmark, tabbed_browser, qtbot, message_bridge,
                        mode_manager):
    """Benchmark showing/drawing of hint labels."""
    tab = tabbed_browser.widget.tabs[0]

    with qtbot.wait_signal(tab.load_finished):
        tab.load_url(QUrl('qute://testdata/data/hints/benchmark.html'))

    manager = qutebrowser.browser.hints.HintManager(win_id=0)

    def bench():
        with qtbot.wait_signal(mode_manager.entered):
            manager.start()

        with qtbot.wait_signal(mode_manager.left):
            mode_manager.leave(usertypes.KeyMode.hint)

    benchmark(bench)


def test_match_benchmark(benchmark, tabbed_browser, qtbot, message_bridge,
                         mode_manager, qapp, config_stub):
    """Benchmark matching of hint labels."""
    tab = tabbed_browser.widget.tabs[0]

    with qtbot.wait_signal(tab.load_finished):
        tab.load_url(QUrl('qute://testdata/data/hints/benchmark.html'))

    config_stub.val.hints.scatter = False
    manager = qutebrowser.browser.hints.HintManager(win_id=0)

    with qtbot.wait_signal(mode_manager.entered):
        manager.start()

    def bench():
        manager.handle_partial_key('a')
        qapp.processEvents()
        manager.handle_partial_key('')
        qapp.processEvents()

    benchmark(bench)

    with qtbot.wait_signal(mode_manager.left):
        mode_manager.leave(usertypes.KeyMode.hint)


@pytest.mark.parametrize('min_len', [0, 3])
@pytest.mark.parametrize('num_chars', [5, 9])
@pytest.mark.parametrize('num_elements', itertools.chain(range(1, 26), [125]))
def test_scattered_hints_count(min_len, num_chars, num_elements):
    """Test scattered hints function.

    Tests many properties from an invocation of _hint_scattered, including

    1. Hints must be unique
    2. There can only be two hint lengths, only 1 apart
    3. There are no unique prefixes for long hints, such as 'la' with no 'l<x>'
    """
    manager = qutebrowser.browser.hints.HintManager(win_id=0)
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

    longest_hint_len = max(hint_lens)
    shortest_hint_len = min(hint_lens)
    longest_hints = [x for x in hints if len(x) == longest_hint_len]

    if min_len < max(hint_lens) - 1:
        # Check if we have any unique prefixes. For example, 'la'
        # alone, with no other 'l<x>'
        count_map = {}
        for x in longest_hints:
            prefix = x[:-1]
            count_map[prefix] = count_map.get(prefix, 0) + 1
        assert all(e != 1 for e in count_map.values())

    # Check that the longest hint length isn't too long
    if longest_hint_len > min_len and longest_hint_len > 1:
        assert num_chars ** (longest_hint_len - 1) < num_elements

    # Check longest hint is not too short
    assert num_chars ** longest_hint_len >= num_elements

    if longest_hint_len > min_len and longest_hint_len > 1:
        # Check that the longest hint length isn't too long
        assert num_chars ** (longest_hint_len - 1) < num_elements
        if shortest_hint_len == longest_hint_len:
            # Check that we really couldn't use any short links
            assert ((num_chars ** longest_hint_len) - num_elements <
                    len(chars) - 1)
