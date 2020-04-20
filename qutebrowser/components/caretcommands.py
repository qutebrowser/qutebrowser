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

"""Commands related to caret browsing."""


from qutebrowser.api import cmdutils, apitypes


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def move_to_next_line(tab: apitypes.Tab, count: int = 1) -> None:
    """Move the cursor or selection to the next line.

    Args:
        count: How many lines to move.
    """
    tab.caret.move_to_next_line(count)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def move_to_prev_line(tab: apitypes.Tab, count: int = 1) -> None:
    """Move the cursor or selection to the prev line.

    Args:
        count: How many lines to move.
    """
    tab.caret.move_to_prev_line(count)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def move_to_next_char(tab: apitypes.Tab, count: int = 1) -> None:
    """Move the cursor or selection to the next char.

    Args:
        count: How many lines to move.
    """
    tab.caret.move_to_next_char(count)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def move_to_prev_char(tab: apitypes.Tab, count: int = 1) -> None:
    """Move the cursor or selection to the previous char.

    Args:
        count: How many chars to move.
    """
    tab.caret.move_to_prev_char(count)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def move_to_end_of_word(tab: apitypes.Tab, count: int = 1) -> None:
    """Move the cursor or selection to the end of the word.

    Args:
        count: How many words to move.
    """
    tab.caret.move_to_end_of_word(count)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def move_to_next_word(tab: apitypes.Tab, count: int = 1) -> None:
    """Move the cursor or selection to the next word.

    Args:
        count: How many words to move.
    """
    tab.caret.move_to_next_word(count)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def move_to_prev_word(tab: apitypes.Tab, count: int = 1) -> None:
    """Move the cursor or selection to the previous word.

    Args:
        count: How many words to move.
    """
    tab.caret.move_to_prev_word(count)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def move_to_start_of_line(tab: apitypes.Tab) -> None:
    """Move the cursor or selection to the start of the line."""
    tab.caret.move_to_start_of_line()


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def move_to_end_of_line(tab: apitypes.Tab) -> None:
    """Move the cursor or selection to the end of line."""
    tab.caret.move_to_end_of_line()


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def move_to_start_of_next_block(tab: apitypes.Tab, count: int = 1) -> None:
    """Move the cursor or selection to the start of next block.

    Args:
        count: How many blocks to move.
    """
    tab.caret.move_to_start_of_next_block(count)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def move_to_start_of_prev_block(tab: apitypes.Tab, count: int = 1) -> None:
    """Move the cursor or selection to the start of previous block.

    Args:
        count: How many blocks to move.
    """
    tab.caret.move_to_start_of_prev_block(count)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def move_to_end_of_next_block(tab: apitypes.Tab, count: int = 1) -> None:
    """Move the cursor or selection to the end of next block.

    Args:
        count: How many blocks to move.
    """
    tab.caret.move_to_end_of_next_block(count)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def move_to_end_of_prev_block(tab: apitypes.Tab, count: int = 1) -> None:
    """Move the cursor or selection to the end of previous block.

    Args:
        count: How many blocks to move.
    """
    tab.caret.move_to_end_of_prev_block(count)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def move_to_start_of_document(tab: apitypes.Tab) -> None:
    """Move the cursor or selection to the start of the document."""
    tab.caret.move_to_start_of_document()


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def move_to_end_of_document(tab: apitypes.Tab) -> None:
    """Move the cursor or selection to the end of the document."""
    tab.caret.move_to_end_of_document()


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def toggle_selection(tab: apitypes.Tab, line: bool = False) -> None:
    """Toggle caret selection mode.

    Args:
        line: Enables line-selection.
    """
    tab.caret.toggle_selection(line)


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def drop_selection(tab: apitypes.Tab) -> None:
    """Drop selection and keep selection mode enabled."""
    tab.caret.drop_selection()


@cmdutils.register()
@cmdutils.argument('tab_obj', value=cmdutils.Value.cur_tab)
def follow_selected(tab_obj: apitypes.Tab, *, tab: bool = False) -> None:
    """Follow the selected text.

    Args:
        tab: Load the selected link in a new tab.
    """
    try:
        tab_obj.caret.follow_selected(tab=tab)
    except apitypes.WebTabError as e:
        raise cmdutils.CommandError(str(e))


@cmdutils.register(modes=[cmdutils.KeyMode.caret])
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def reverse_selection(tab: apitypes.Tab) -> None:
    """Swap the stationary and moving end of the current selection."""
    tab.caret.reverse_selection()
