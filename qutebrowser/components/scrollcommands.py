# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Scrolling-related commands."""

from collections.abc import Callable
from qutebrowser.api import cmdutils, apitypes


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def scroll_px(tab: apitypes.Tab, dx: int, dy: int, count: int = 1) -> None:
    """Scroll the current tab by 'count * dx/dy' pixels.

    Args:
        dx: How much to scroll in x-direction.
        dy: How much to scroll in y-direction.
        count: multiplier
    """
    dx *= count
    dy *= count
    cmdutils.check_overflow(dx, 'int')
    cmdutils.check_overflow(dy, 'int')
    tab.scroller.delta(dx, dy)


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
def scroll(tab: apitypes.Tab, direction: str, count: int = 1) -> None:
    """Scroll the current tab in the given direction.

    Note you can use `:cmd-run-with-count` to have a keybinding with a bigger
    scroll increment.

    Args:
        direction: In which direction to scroll
                    (up/down/left/right/top/bottom).
        count: multiplier
    """
    # FIXME:mypy Use a callback protocol to enforce having 'count'?
    funcs: dict[str, Callable[..., None]] = {
        'up': tab.scroller.up,
        'down': tab.scroller.down,
        'left': tab.scroller.left,
        'right': tab.scroller.right,
        'top': tab.scroller.top,
        'bottom': tab.scroller.bottom,
        'page-up': tab.scroller.page_up,
        'page-down': tab.scroller.page_down,
    }
    try:
        func = funcs[direction]
    except KeyError:
        expected_values = ', '.join(sorted(funcs))
        raise cmdutils.CommandError("Invalid value {!r} for direction - "
                                    "expected one of: {}".format(
                                        direction, expected_values))

    if direction in ['top', 'bottom']:
        func()
    else:
        func(count=count)


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
@cmdutils.argument('count', value=cmdutils.Value.count)
@cmdutils.argument('horizontal', flag='x')
def scroll_to_perc(tab: apitypes.Tab, count: int = None,
                   perc: float = None, horizontal: bool = False) -> None:
    """Scroll to a specific percentage of the page.

    The percentage can be given either as argument or as count.
    If no percentage is given, the page is scrolled to the end.

    Args:
        perc: Percentage to scroll.
        horizontal: Scroll horizontally instead of vertically.
        count: Percentage to scroll.
    """
    if perc is None and count is None:
        perc = 100
    elif count is not None:
        perc = count

    if horizontal:
        x = perc
        y = None
    else:
        x = None
        y = perc

    tab.scroller.before_jump_requested.emit()
    tab.scroller.to_perc(x, y)


@cmdutils.register()
@cmdutils.argument('tab', value=cmdutils.Value.cur_tab)
def scroll_to_anchor(tab: apitypes.Tab, name: str) -> None:
    """Scroll to the given anchor in the document.

    Args:
        name: The anchor to scroll to.
    """
    tab.scroller.before_jump_requested.emit()
    tab.scroller.to_anchor(name)
