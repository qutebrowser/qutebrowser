# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for caret browsing mode."""

import textwrap

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.utils import usertypes
from qutebrowser.browser import browsertab


@pytest.fixture
def caret(web_tab, qtbot, mode_manager):
    web_tab.container.expose()

    with qtbot.wait_signal(web_tab.load_finished, timeout=10000):
        web_tab.load_url(QUrl('qute://testdata/data/caret.html'))

    with qtbot.wait_signal(web_tab.caret.selection_toggled):
        mode_manager.enter(usertypes.KeyMode.caret)

    return web_tab.caret


class Selection:

    """Helper to interact with the caret selection."""

    def __init__(self, qtbot, caret):
        self._qtbot = qtbot
        self._caret = caret

    def check(self, expected, *, strip=False):
        """Check whether we got the expected selection.

        Since (especially on Windows) the selection is empty if we're checking
        too quickly, we try to read it multiple times.
        """
        for _ in range(10):
            with self._qtbot.wait_callback() as callback:
                self._caret.selection(callback)

            selection = callback.args[0]
            if selection:
                if strip:
                    selection = selection.strip()
                assert selection == expected
                return
            elif not selection and not expected:
                return

            self._qtbot.wait(50)

        assert False, 'Failed to get selection!'

    def check_multiline(self, expected, *, strip=False):
        self.check(textwrap.dedent(expected).strip(), strip=strip)

    def toggle(self, *, line=False):
        """Toggle the selection and return the new selection state."""
        with self._qtbot.wait_signal(self._caret.selection_toggled) as blocker:
            self._caret.toggle_selection(line=line)
        return blocker.args[0]


@pytest.fixture
def selection(qtbot, caret):
    return Selection(qtbot, caret)


def test_toggle(caret, selection, qtbot):
    """Make sure calling toggleSelection produces the correct callback values.

    This also makes sure that the SelectionState enum in JS lines up with the
    Python browsertab.SelectionState enum.
    """
    assert selection.toggle() == browsertab.SelectionState.normal
    assert selection.toggle(line=True) == browsertab.SelectionState.line
    assert selection.toggle() == browsertab.SelectionState.normal
    assert selection.toggle() == browsertab.SelectionState.none


class TestDocument:

    def test_selecting_entire_document(self, caret, selection):
        selection.toggle()
        caret.move_to_end_of_document()
        selection.check_multiline("""
            one two three
            eins zwei drei

            four five six
            vier fünf sechs
        """, strip=True)

    def test_moving_to_end_and_start(self, caret, selection):
        caret.move_to_end_of_document()
        caret.move_to_start_of_document()
        selection.toggle()
        caret.move_to_end_of_word()
        selection.check("one")

    def test_moving_to_end_and_start_with_selection(self, caret, selection):
        caret.move_to_end_of_document()
        selection.toggle()
        caret.move_to_start_of_document()
        selection.check_multiline("""
            one two three
            eins zwei drei

            four five six
            vier fünf sechs
        """, strip=True)


class TestBlock:

    def test_selecting_block(self, caret, selection):
        selection.toggle()
        caret.move_to_end_of_next_block()
        selection.check_multiline("""
            one two three
            eins zwei drei
        """)

    def test_moving_back_to_the_end_of_prev_block_with_sel(self, caret, selection):
        caret.move_to_end_of_next_block(2)
        selection.toggle()
        caret.move_to_end_of_prev_block()
        caret.move_to_prev_word()
        selection.check_multiline("""
            drei

            four five six
        """)

    def test_moving_back_to_the_end_of_prev_block(self, caret, selection):
        caret.move_to_end_of_next_block(2)
        caret.move_to_end_of_prev_block()
        selection.toggle()
        caret.move_to_prev_word()
        selection.check("drei")

    def test_moving_back_to_the_start_of_prev_block_with_sel(self, caret, selection):
        caret.move_to_end_of_next_block(2)
        selection.toggle()
        caret.move_to_start_of_prev_block()
        selection.check_multiline("""
            eins zwei drei

            four five six
        """)

    def test_moving_back_to_the_start_of_prev_block(self, caret, selection):
        caret.move_to_end_of_next_block(2)
        caret.move_to_start_of_prev_block()
        selection.toggle()
        caret.move_to_next_word()
        selection.check("eins ")

    def test_moving_to_the_start_of_next_block_with_sel(self, caret, selection):
        selection.toggle()
        caret.move_to_start_of_next_block()
        selection.check("one two three\n")

    def test_moving_to_the_start_of_next_block(self, caret, selection):
        caret.move_to_start_of_next_block()
        selection.toggle()
        caret.move_to_end_of_word()
        selection.check("eins")


class TestLine:

    def test_selecting_a_line(self, caret, selection):
        selection.toggle()
        caret.move_to_end_of_line()
        selection.check("one two three")

    def test_moving_and_selecting_a_line(self, caret, selection):
        caret.move_to_next_line()
        selection.toggle()
        caret.move_to_end_of_line()
        selection.check("eins zwei drei")

    def test_selecting_next_line(self, caret, selection):
        selection.toggle()
        caret.move_to_next_line()
        selection.check("one two three\n")

    def test_moving_to_end_and_to_start_of_line(self, caret, selection):
        caret.move_to_end_of_line()
        caret.move_to_start_of_line()
        selection.toggle()
        caret.move_to_end_of_word()
        selection.check("one")

    def test_selecting_a_line_backwards(self, caret, selection):
        caret.move_to_end_of_line()
        selection.toggle()
        caret.move_to_start_of_line()
        selection.check("one two three")

    def test_selecting_previous_line(self, caret, selection):
        caret.move_to_next_line()
        selection.toggle()
        caret.move_to_prev_line()
        selection.check("one two three\n")

    def test_moving_to_previous_line(self, caret, selection):
        caret.move_to_next_line()
        caret.move_to_prev_line()
        selection.toggle()
        caret.move_to_next_line()
        selection.check("one two three\n")


class TestWord:

    def test_selecting_a_word(self, caret, selection):
        selection.toggle()
        caret.move_to_end_of_word()
        selection.check("one")

    def test_moving_to_end_and_selecting_a_word(self, caret, selection):
        caret.move_to_end_of_word()
        selection.toggle()
        caret.move_to_end_of_word()
        selection.check(" two")

    def test_moving_to_next_word_and_selecting_a_word(self, caret, selection):
        caret.move_to_next_word()
        selection.toggle()
        caret.move_to_end_of_word()
        selection.check("two")

    def test_moving_to_next_word_and_selecting_until_next_word(self, caret, selection):
        caret.move_to_next_word()
        selection.toggle()
        caret.move_to_next_word()
        selection.check("two ")

    def test_moving_to_previous_word_and_selecting_a_word(self, caret, selection):
        caret.move_to_end_of_word()
        selection.toggle()
        caret.move_to_prev_word()
        selection.check("one")

    def test_moving_to_previous_word(self, caret, selection):
        caret.move_to_end_of_word()
        caret.move_to_prev_word()
        selection.toggle()
        caret.move_to_end_of_word()
        selection.check("one")


class TestChar:

    def test_selecting_a_char(self, caret, selection):
        selection.toggle()
        caret.move_to_next_char()
        selection.check("o")

    def test_moving_and_selecting_a_char(self, caret, selection):
        caret.move_to_next_char()
        selection.toggle()
        caret.move_to_next_char()
        selection.check("n")

    def test_selecting_previous_char(self, caret, selection):
        caret.move_to_end_of_word()
        selection.toggle()
        caret.move_to_prev_char()
        selection.check("e")

    def test_moving_to_previous_char(self, caret, selection):
        caret.move_to_end_of_word()
        caret.move_to_prev_char()
        selection.toggle()
        caret.move_to_end_of_word()
        selection.check("e")


def test_drop_selection(caret, selection):
    selection.toggle()
    caret.move_to_end_of_word()
    caret.drop_selection()
    selection.check("")


class TestSearch:

    # https://bugreports.qt.io/browse/QTBUG-60673

    @pytest.mark.qtbug60673
    @pytest.mark.no_xvfb
    def test_yanking_a_searched_line(self, caret, selection, mode_manager, web_tab, qtbot):
        mode_manager.leave(usertypes.KeyMode.caret)

        with qtbot.wait_callback() as callback:
            web_tab.search.search('fiv', result_cb=callback)
        callback.assert_called_with(True)

        mode_manager.enter(usertypes.KeyMode.caret)
        caret.move_to_end_of_line()
        selection.check('five six')

    @pytest.mark.qtbug60673
    @pytest.mark.no_xvfb
    def test_yanking_a_searched_line_with_multiple_matches(self, caret, selection, mode_manager, web_tab, qtbot):
        mode_manager.leave(usertypes.KeyMode.caret)

        with qtbot.wait_callback() as callback:
            web_tab.search.search('w', result_cb=callback)
        callback.assert_called_with(True)

        with qtbot.wait_callback() as callback:
            web_tab.search.next_result(result_cb=callback)
        callback.assert_called_with(True)

        mode_manager.enter(usertypes.KeyMode.caret)

        caret.move_to_end_of_line()
        selection.check('wei drei')


class TestFollowSelected:

    LOAD_STARTED_DELAY = 50

    @pytest.fixture(params=[True, False], autouse=True)
    def toggle_js(self, request, config_stub):
        config_stub.val.content.javascript.enabled = request.param

    def test_follow_selected_without_a_selection(self, qtbot, caret, selection, web_tab,
                                                 mode_manager):
        caret.move_to_next_word()  # Move cursor away from the link
        mode_manager.leave(usertypes.KeyMode.caret)
        with qtbot.wait_signal(caret.follow_selected_done):
            with qtbot.assert_not_emitted(web_tab.load_started,
                                          wait=self.LOAD_STARTED_DELAY):
                caret.follow_selected()

    def test_follow_selected_with_text(self, qtbot, caret, selection, web_tab):
        caret.move_to_next_word()
        selection.toggle()
        caret.move_to_end_of_word()
        with qtbot.wait_signal(caret.follow_selected_done):
            with qtbot.assert_not_emitted(web_tab.load_started,
                                          wait=self.LOAD_STARTED_DELAY):
                caret.follow_selected()

    def test_follow_selected_with_link(self, caret, selection, config_stub,
                                       qtbot, web_tab):
        selection.toggle()
        caret.move_to_end_of_word()
        with qtbot.wait_signal(web_tab.load_finished):
            with qtbot.wait_signal(caret.follow_selected_done):
                caret.follow_selected()
        assert web_tab.url().path() == '/data/hello.txt'


class TestReverse:

    def test_does_not_change_selection(self, caret, selection):
        selection.toggle()
        caret.reverse_selection()
        selection.check("")

    def test_repetition_of_movement_results_in_empty_selection(self, caret, selection):
        selection.toggle()
        caret.move_to_end_of_word()
        caret.reverse_selection()
        caret.move_to_end_of_word()
        selection.check("")

    def test_reverse(self, caret, selection):
        selection.toggle()
        caret.move_to_end_of_word()
        caret.reverse_selection()
        caret.move_to_next_char()
        selection.check("ne")
        caret.reverse_selection()
        caret.move_to_next_char()
        selection.check("ne ")
        caret.move_to_end_of_line()
        selection.check("ne two three")
        caret.reverse_selection()
        caret.move_to_start_of_line()
        selection.check("one two three")


class TestLineSelection:

    def test_toggle(self, caret, selection):
        selection.toggle(line=True)
        selection.check("one two three")

    def test_toggle_untoggle(self, caret, selection):
        selection.toggle()
        selection.check("")
        selection.toggle(line=True)
        selection.check("one two three")
        selection.toggle()
        selection.check("one two three")

    def test_from_center(self, caret, selection):
        caret.move_to_next_char(4)
        selection.toggle(line=True)
        selection.check("one two three")

    def test_more_lines(self, caret, selection):
        selection.toggle(line=True)
        caret.move_to_next_line(2)
        selection.check_multiline("""
            one two three
            eins zwei drei

            four five six
        """, strip=True)

    def test_not_selecting_char(self, caret, selection):
        selection.toggle(line=True)
        caret.move_to_next_char()
        selection.check("one two three")
        caret.move_to_prev_char()
        selection.check("one two three")

    def test_selecting_prev_next_word(self, caret, selection):
        selection.toggle(line=True)
        caret.move_to_next_word()
        selection.check("one two three")
        caret.move_to_prev_word()
        selection.check("one two three")

    def test_selecting_end_word(self, caret, selection):
        selection.toggle(line=True)
        caret.move_to_end_of_word()
        selection.check("one two three")

    def test_selecting_prev_next_line(self, caret, selection):
        selection.toggle(line=True)
        caret.move_to_next_line()
        selection.check_multiline("""
            one two three
            eins zwei drei
        """, strip=True)
        caret.move_to_prev_line()
        selection.check("one two three")

    def test_not_selecting_start_end_line(self, caret, selection):
        selection.toggle(line=True)
        caret.move_to_end_of_line()
        selection.check("one two three")
        caret.move_to_start_of_line()
        selection.check("one two three")

    def test_selecting_block(self, caret, selection):
        selection.toggle(line=True)
        caret.move_to_end_of_next_block()
        selection.check_multiline("""
            one two three
            eins zwei drei
        """, strip=True)

    @pytest.mark.not_mac(
        reason='https://github.com/qutebrowser/qutebrowser/issues/5459')
    def test_selecting_start_end_document(self, caret, selection):
        selection.toggle(line=True)
        caret.move_to_end_of_document()
        selection.check_multiline("""
            one two three
            eins zwei drei

            four five six
            vier fünf sechs
        """, strip=True)

        caret.move_to_start_of_document()
        selection.check("one two three")
