# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import string
import functools
import itertools
import operator

import pytest
from qutebrowser.qt.core import QUrl

from qutebrowser.utils import usertypes
import qutebrowser.browser.hints


@pytest.fixture(autouse=True)
def setup(win_registry, mode_manager):
    pass


@pytest.fixture
def tabbed_browser(tabbed_browser_stubs, web_tab):
    tb = tabbed_browser_stubs[0]
    tb.widget.tabs = [web_tab]
    tb.widget.current_index = 1
    tb.widget.cur_url = QUrl('https://www.example.com/')
    web_tab.container.expose()  # No elements found if we don't do this.
    return tb


def test_show_benchmark(benchmark, tabbed_browser, qtbot, mode_manager):
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


def test_match_benchmark(benchmark, tabbed_browser, qtbot, mode_manager, qapp,
                         config_stub):
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


class TestTextFiltering:
    """Tests for the --text parameter hint filtering functionality."""
    
    @pytest.fixture
    def hint_manager(self):
        """Create a HintManager instance for testing."""
        return qutebrowser.browser.hints.HintManager(win_id=0)
    
    @pytest.fixture 
    def mock_elem(self):
        """Create a mock web element for testing."""
        elem = pytest.Mock()
        elem.value.return_value = ""
        elem.get.return_value = ""
        return elem
    
    def test_filter_matches_basic(self, hint_manager):
        """Test basic text filtering functionality."""
        # Test case-insensitive matching
        assert hint_manager._filter_matches("hello", "Hello World")
        assert hint_manager._filter_matches("WORLD", "hello world")
        
        # Test substring matching
        assert hint_manager._filter_matches("ell", "Hello")
        assert not hint_manager._filter_matches("xyz", "Hello")
        
        # Test empty filter (should match everything)
        assert hint_manager._filter_matches("", "anything")
        assert hint_manager._filter_matches(None, "anything")
    
    def test_filter_matches_multiword(self, hint_manager):
        """Test multi-word filtering functionality."""
        text = "Submit the form now"
        
        # Test multi-word matching (all words must be present)
        assert hint_manager._filter_matches("submit form", text)
        assert hint_manager._filter_matches("the now", text)
        assert hint_manager._filter_matches("form submit", text)  # order doesn't matter
        
        # Test partial multi-word matching fails
        assert not hint_manager._filter_matches("submit missing", text)
        assert not hint_manager._filter_matches("form xyz", text)
    
    def test_text_filter_with_placeholder(self, hint_manager, mock_elem):
        """Test text filtering includes placeholder text."""
        # Mock element with placeholder
        mock_elem.__str__.return_value = "Submit"  # text content
        mock_elem.value.return_value = ""  # no value
        mock_elem.get.return_value = "Enter your name"  # placeholder
        
        # Combined text should be "Submit  Enter your name"
        combined = f"Submit   Enter your name".strip()
        
        # Should match placeholder text
        assert hint_manager._filter_matches("Enter", combined)
        assert hint_manager._filter_matches("name", combined)
        assert hint_manager._filter_matches("your name", combined)
        
        # Should still match text content
        assert hint_manager._filter_matches("Submit", combined)
        
        # Should match combination
        assert hint_manager._filter_matches("Submit Enter", combined)
    
    def test_text_filter_with_value(self, hint_manager, mock_elem):
        """Test text filtering includes input values."""
        # Mock element with value
        mock_elem.__str__.return_value = ""  # no text content
        mock_elem.value.return_value = "current input text"  # input value
        mock_elem.get.return_value = "placeholder text"  # placeholder
        
        combined = f" current input text placeholder text".strip()
        
        # Should match input value
        assert hint_manager._filter_matches("current", combined)
        assert hint_manager._filter_matches("input text", combined)
        
        # Should match placeholder
        assert hint_manager._filter_matches("placeholder", combined)
        
        # Should match combination
        assert hint_manager._filter_matches("current placeholder", combined)
    
    def test_text_filter_combined_sources(self, hint_manager, mock_elem):
        """Test text filtering with all text sources combined."""
        # Mock element with all text sources
        mock_elem.__str__.return_value = "Login Button"  # text content
        mock_elem.value.return_value = "login"  # input value  
        mock_elem.get.return_value = "Enter credentials"  # placeholder
        
        combined = "Login Button login Enter credentials"
        
        # Should match any individual source
        assert hint_manager._filter_matches("Button", combined)
        assert hint_manager._filter_matches("login", combined)  # matches both text and value
        assert hint_manager._filter_matches("credentials", combined)
        
        # Should match across sources
        assert hint_manager._filter_matches("Login Enter", combined)
        assert hint_manager._filter_matches("Button credentials", combined)
    
    def test_text_filter_empty_sources(self, hint_manager, mock_elem):
        """Test text filtering with empty/None values."""
        # Mock element with empty values
        mock_elem.__str__.return_value = "Button Text"
        mock_elem.value.return_value = None  # None value
        mock_elem.get.return_value = ""  # empty placeholder
        
        combined = "Button Text  ".strip()
        
        # Should still work with just text content
        assert hint_manager._filter_matches("Button", combined)
        assert hint_manager._filter_matches("Text", combined)
        assert not hint_manager._filter_matches("missing", combined)
    
    def test_hint_context_text_filter(self):
        """Test HintContext includes text_filter field."""
        from qutebrowser.browser.hints import HintContext
        from qutebrowser.qt.core import QUrl
        
        # Create a minimal HintContext to test text_filter field
        context = HintContext(
            tab=pytest.Mock(),
            target=pytest.Mock(),
            rapid=False,
            hint_mode="number",
            add_history=False,
            first=False,
            baseurl=QUrl("https://example.com"),
            args=[],
            group="all",
            text_filter="test filter"
        )
        
        assert context.text_filter == "test filter"
        
        # Test with None (default)
        context_none = HintContext(
            tab=pytest.Mock(),
            target=pytest.Mock(),
            rapid=False,
            hint_mode="number",
            add_history=False,
            first=False,
            baseurl=QUrl("https://example.com"),
            args=[],
            group="all"
        )
        
        assert context_none.text_filter is None
