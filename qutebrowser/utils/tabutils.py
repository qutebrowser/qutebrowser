# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2019 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


"""Utilities to list and manipulate browser tabs."""

import typing
from functools import partial

from PyQt5.QtCore import QUrl
from qutebrowser.api import cmdutils
from qutebrowser.completion.models import miscmodels
from qutebrowser.utils import objreg

if typing.TYPE_CHECKING:
    from qutebrowser.browser import browsertab


def all_tabs(skip_win_id: bool = None
             ) -> typing.Iterator["browsertab.AbstractTab"]:
    """Return a list generator expression of all tabs across all windows."""
    for win_id in objreg.window_registry:
        if win_id == skip_win_id:
            continue

        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)

        if tabbed_browser.shutting_down:
            continue

        for idx in range(tabbed_browser.widget.count()):
            yield tabbed_browser.widget.widget(idx)


def all_tabs_by_window(skip_win_id: bool = None) -> typing.Dict[
        int, typing.List['browsertab.AbstractTab']]:
    """Return a dictionary of all tabs by window id."""
    tabs = {}  # type: typing.Dict[int, typing.List[browsertab.AbstractTab]]

    for win_id in objreg.window_registry:
        if win_id == skip_win_id:
            continue

        tabs[win_id] = []

        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)

        if tabbed_browser.shutting_down:
            continue

        for idx in range(tabbed_browser.widget.count()):
            tabs[win_id].append(tabbed_browser.widget.widget(idx))

    return tabs


def switch_to_tab(tab: 'browsertab.AbstractTab') -> None:
    """Try to switch to an existing tab."""
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=tab.win_id)

    window = tabbed_browser.widget.window()
    window.activateWindow()
    window.raise_()
    tabbed_browser.widget.setCurrentWidget(tab)


def tab_for_url(url: typing.Union[str, QUrl]) -> typing.Union[
        None, 'browsertab.AbstractTab']:
    """Returns the tab that has the URL open."""
    qurl = QUrl(url)
    tab = next((t for t in all_tabs() if t.url() == url or t.url() == qurl),
               None)

    return tab


def _delete_tab_func(i: int, data: typing.List[str]) -> None:
    """Used as a delete_func in completions. Close the selected tab.

    Args:
        data: a tuple/list representing a tab (url, title, win_id and index)
    """
    win_id, tab_index = data[i].split('/')
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=int(win_id))

    tabbed_browser.on_tab_close_requested(int(tab_index) - 1)


def delete_tab(i: int) -> typing.Callable[[typing.Sequence[str]], None]:
    """Used as a delete_func in completions. Close the selected tab.

    Returns a function that can be used as a delete_func.

    Args:
        i: the place of the index in the data tuple/list
    """
    return partial(_delete_tab_func, i)


def resolve_tab_index(index: str) -> 'browsertab.AbstractTab':
    """Resolve a tab index string to the win_id and tab index.

    Args:
        index: The [win_id/]index of the tab to be selected. Or a substring
                in which case the closest match will be focused.
    """
    index_parts = index.split('/', 1)

    try:
        for part in index_parts:
            int(part)
    except ValueError:
        model = miscmodels.buffer()
        model.set_pattern(index)

        if model.count() > 0:
            index = model.data(model.first_item())
            index_parts = index.split('/', 1)
        else:
            raise cmdutils.CommandError(
                "No matching tab for: {}".format(index))

    if len(index_parts) == 2:
        win_id = int(index_parts[0])
        idx = int(index_parts[1])
    elif len(index_parts) == 1:
        idx = int(index_parts[0])
        active_win = objreg.get('app').activeWindow()

        if active_win is None:
            # Not sure how you enter a command without an active window...
            raise cmdutils.CommandError(
                "No window specified and couldn't find active window!")
        win_id = active_win.win_id

    if win_id not in objreg.window_registry:
        raise cmdutils.CommandError(
            "There's no window with id {}!".format(win_id))

    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=win_id)

    if not 0 < idx <= tabbed_browser.widget.count():
        raise cmdutils.CommandError(
            "There's no tab with index {}!".format(idx))

    return tabbed_browser.widget.widget(idx - 1)
