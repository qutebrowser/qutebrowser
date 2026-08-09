# SPDX-FileCopyrightText: Freya Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utilities to list and manipulate browser tabs."""

from functools import partial
from typing import Optional, TYPE_CHECKING
from collections.abc import Callable, Iterator, Sequence

from qutebrowser.qt.core import QUrl

from qutebrowser.config import config
from qutebrowser.utils import objreg

if TYPE_CHECKING:
    from qutebrowser.browser import browsertab


def all_tabs(
    skip_win_id: Optional[int] = None,
) -> Iterator['browsertab.AbstractTab']:
    """Yield all tabs across all windows.

    Args:
        skip_win_id: A window id to skip, e.g. the current one.
    """
    for win_id in objreg.window_registry:
        if win_id == skip_win_id:
            continue

        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)

        if tabbed_browser.is_shutting_down:
            continue

        for idx in range(tabbed_browser.widget.count()):
            yield tabbed_browser.widget.widget(idx)


def all_tabs_by_window(
    skip_win_id: Optional[int] = None,
) -> dict[int, list['browsertab.AbstractTab']]:
    """Return a dict mapping each window id to its list of tabs.

    Args:
        skip_win_id: A window id to skip, e.g. the current one.
    """
    tabs: dict[int, list['browsertab.AbstractTab']] = {}

    for win_id in objreg.window_registry:
        if win_id == skip_win_id:
            continue

        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)

        if tabbed_browser.is_shutting_down:
            continue

        tabs[win_id] = []
        for idx in range(tabbed_browser.widget.count()):
            tabs[win_id].append(tabbed_browser.widget.widget(idx))

    return tabs


def switch_to_tab(tab: 'browsertab.AbstractTab') -> None:
    """Switch to an existing tab, raising its window."""
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=tab.win_id)

    window = tabbed_browser.widget.window()
    window.activateWindow()
    window.raise_()
    tabbed_browser.widget.setCurrentWidget(tab)


def tab_for_url(
    url: QUrl,
    *,
    private: bool,
) -> Optional['browsertab.AbstractTab']:
    """Return the first tab that has the given URL open.

    Only tabs matching the given privacy context are considered, so a switch
    never crosses the private-browsing boundary.

    Args:
        url: The URL to look for.
        private: Only match tabs whose privacy mode equals this value.
    """
    return next(
        (tab for tab in all_tabs()
         if bool(tab.is_private) == bool(private) and tab.url() == url),
        None)


def switch_to_open_url(
    url: QUrl,
    *,
    private: Optional[bool],
    reuse: bool = True,
) -> Optional['browsertab.AbstractTab']:
    """Switch to a tab already showing url, if tabs.switch_to_open_url is set.

    Returns the tab switched to, or None if nothing was switched (feature off,
    reuse suppressed, or no matching tab in the same privacy context).

    Args:
        url: The URL to switch to.
        private: The privacy context to match (see tab_for_url).
        reuse: Pass False to force a fresh open (e.g. when taking a tab).
    """
    if not (reuse and config.val.tabs.switch_to_open_url):
        return None
    tab = tab_for_url(url, private=bool(private))
    if tab is not None:
        switch_to_tab(tab)
    return tab


def _delete_tab_func(i: int, data: Sequence[str]) -> None:
    """Close the tab described by a completion data tuple.

    Args:
        i: The index of the "win_id/index" entry in the data tuple.
        data: A tuple/list representing a tab (url, title, "win_id/index").
    """
    win_id, tab_index = data[i].split('/')
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=int(win_id))

    tabbed_browser.on_tab_close_requested(int(tab_index) - 1)


def delete_tab(i: int) -> Callable[[Sequence[str]], None]:
    """Build a delete_func for completions which closes the selected tab.

    Args:
        i: The index of the "win_id/index" entry in the data tuple.
    """
    return partial(_delete_tab_func, i)
