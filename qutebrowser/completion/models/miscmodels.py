# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Functions that return miscellaneous completion models."""

import datetime
import itertools
from typing import List, Sequence, Tuple

from qutebrowser.config import config, configdata
from qutebrowser.utils import objreg, log, utils
from qutebrowser.completion.models import completionmodel, listcategory, util
from qutebrowser.browser import inspector


def command(*, info):
    """A CompletionModel filled with non-hidden commands and descriptions."""
    model = completionmodel.CompletionModel(column_widths=(20, 60, 20))
    cmdlist = util.get_cmd_completions(info, include_aliases=True,
                                       include_hidden=False)
    model.add_category(listcategory.ListCategory("Commands", cmdlist))
    return model


def helptopic(*, info):
    """A CompletionModel filled with help topics."""
    model = completionmodel.CompletionModel(column_widths=(20, 70, 10))

    cmdlist = util.get_cmd_completions(info, include_aliases=False,
                                       include_hidden=True, prefix=':')
    settings = ((opt.name, opt.description, info.config.get_str(opt.name))
                for opt in configdata.DATA.values())

    model.add_category(listcategory.ListCategory("Commands", cmdlist))
    model.add_category(listcategory.ListCategory("Settings", settings))
    return model


def quickmark(*, info=None):
    """A CompletionModel filled with all quickmarks."""
    def delete(data: Sequence[str]) -> None:
        """Delete a quickmark from the completion menu."""
        name = data[0]
        quickmark_manager = objreg.get('quickmark-manager')
        log.completion.debug('Deleting quickmark {}'.format(name))
        quickmark_manager.delete(name)

    utils.unused(info)
    model = completionmodel.CompletionModel(column_widths=(30, 70, 0))
    marks = objreg.get('quickmark-manager').marks.items()
    model.add_category(listcategory.ListCategory('Quickmarks', marks,
                                                 delete_func=delete,
                                                 sort=False))
    return model


def bookmark(*, info=None):
    """A CompletionModel filled with all bookmarks."""
    def delete(data: Sequence[str]) -> None:
        """Delete a bookmark from the completion menu."""
        urlstr = data[0]
        log.completion.debug('Deleting bookmark {}'.format(urlstr))
        bookmark_manager = objreg.get('bookmark-manager')
        bookmark_manager.delete(urlstr)

    utils.unused(info)
    model = completionmodel.CompletionModel(column_widths=(30, 70, 0))
    marks = objreg.get('bookmark-manager').marks.items()
    model.add_category(listcategory.ListCategory('Bookmarks', marks,
                                                 delete_func=delete,
                                                 sort=False))
    return model


def session(*, info=None):
    """A CompletionModel filled with session names."""
    from qutebrowser.misc import sessions
    utils.unused(info)
    model = completionmodel.CompletionModel()
    try:
        sess = ((name,) for name
                in sessions.session_manager.list_sessions()
                if not name.startswith('_'))
        model.add_category(listcategory.ListCategory("Sessions", sess))
    except OSError:
        log.completion.exception("Failed to list sessions!")
    return model


def _tabs(*, win_id_filter=lambda _win_id: True, add_win_id=True):
    """Helper to get the completion model for tabs/other_tabs.

    Args:
        win_id_filter: A filter function for window IDs to include.
                       Should return True for all included windows.
        add_win_id: Whether to add the window ID to the completion items.
    """
    def delete_tab(data):
        """Close the selected tab."""
        win_id, tab_index = data[0].split('/')
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=int(win_id))
        tabbed_browser.on_tab_close_requested(int(tab_index) - 1)

    model = completionmodel.CompletionModel(column_widths=(6, 40, 46, 8))

    tabs_are_windows = config.val.tabs.tabs_are_windows
    # list storing all single-tabbed windows when tabs_are_windows
    windows: List[Tuple[str, str, str, str]] = []

    for win_id in objreg.window_registry:
        if not win_id_filter(win_id):
            continue

        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)
        if tabbed_browser.is_shutting_down:
            continue
        tab_entries: List[Tuple[str, str, str, str]] = []
        for idx in range(tabbed_browser.widget.count()):
            tab = tabbed_browser.widget.widget(idx)
            tab_str = ("{}/{}".format(win_id, idx + 1) if add_win_id
                       else str(idx + 1))

            pid = tab.renderer_process_pid()

            tab_entries.append((
                tab_str,
                tab.url().toDisplayString(),
                tabbed_browser.widget.page_title(idx),
                "" if pid is None else f"PID {pid}",
            ))

        if tabs_are_windows:
            windows += tab_entries
        else:
            title = str(win_id) if add_win_id else "Tabs"
            cat = listcategory.ListCategory(
                title, tab_entries, delete_func=delete_tab, sort=False)
            model.add_category(cat)

    if tabs_are_windows:
        win = listcategory.ListCategory(
            "Windows", windows, delete_func=delete_tab, sort=False)
        model.add_category(win)

    return model


def tabs(*, info=None):
    """A model to complete on open tabs across all windows.

    Used for the tab-select command (and others).
    """
    utils.unused(info)
    return _tabs()


def other_tabs(*, info):
    """A model to complete on open tabs across all windows except the current.

    Used for the tab-take command.
    """
    return _tabs(win_id_filter=lambda win_id: win_id != info.win_id)


def tab_focus(*, info):
    """A model to complete on open tabs in the current window."""
    model = _tabs(win_id_filter=lambda win_id: win_id == info.win_id,
                  add_win_id=False)

    special = [
        ("last", "Focus the last-focused tab"),
        ("stack-next", "Go forward through a stack of focused tabs"),
        ("stack-prev", "Go backward through a stack of focused tabs"),
    ]
    model.add_category(listcategory.ListCategory("Special", special))

    return model


def window(*, info):
    """A model to complete on all open windows."""
    model = completionmodel.CompletionModel(column_widths=(6, 30, 64))

    windows = []

    for win_id in objreg.window_registry:
        if win_id == info.win_id:
            continue
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=win_id)
        tab_titles = (tab.title() for tab in tabbed_browser.widgets())
        windows.append(("{}".format(win_id),
                        objreg.window_registry[win_id].windowTitle(),
                        ", ".join(tab_titles)))

    model.add_category(listcategory.ListCategory("Windows", windows))

    return model


def inspector_position(*, info):
    """A model for possible inspector positions."""
    utils.unused(info)
    model = completionmodel.CompletionModel(column_widths=(100, 0, 0))
    positions = [(e.name,) for e in inspector.Position]
    category = listcategory.ListCategory("Position (optional)", positions)
    model.add_category(category)
    return model


def _qdatetime_to_completion_format(qdate):
    if not qdate.isValid():
        ts = 0
    else:
        ts = qdate.toMSecsSinceEpoch()
        if ts < 0:
            ts = 0
    pydate = datetime.datetime.fromtimestamp(ts / 1000)
    return pydate.strftime(config.val.completion.timestamp_format)


def _back_forward(info, go_forward):
    history = info.cur_tab.history
    current_idx = history.current_idx()
    model = completionmodel.CompletionModel(column_widths=(5, 36, 50, 9))

    if go_forward:
        start = current_idx + 1
        items = history.forward_items()
    else:
        start = 0
        items = history.back_items()

    entries = [
        (
            str(idx),
            entry.url().toDisplayString(),
            entry.title(),
            _qdatetime_to_completion_format(entry.lastVisited())
        )
        for idx, entry in enumerate(items, start)
    ]
    if not go_forward:
        # make sure the most recent is at the top for :back
        entries.reverse()

    cat = listcategory.ListCategory("History", entries, sort=False)
    model.add_category(cat)
    return model


def forward(*, info):
    """A model to complete on history of the current tab.

    Used for the :forward command.
    """
    return _back_forward(info, go_forward=True)


def back(*, info):
    """A model to complete on history of the current tab.

    Used for the :back command.
    """
    return _back_forward(info, go_forward=False)


def undo(*, info):
    """A model to complete undo entries."""
    tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                window=info.win_id)
    model = completionmodel.CompletionModel(column_widths=(6, 84, 10))
    timestamp_format = config.val.completion.timestamp_format

    entries = [
        (
            str(idx),
            ', '.join(entry.url.toDisplayString() for entry in group),
            group[-1].created_at.strftime(timestamp_format)
        )
        for idx, group in
        enumerate(reversed(tabbed_browser.undo_stack), start=1)
    ]

    cat = listcategory.ListCategory("Closed tabs", entries, sort=False)
    model.add_category(cat)
    return model


def process(*, info):
    """A CompletionModel filled with processes."""
    utils.unused(info)
    from qutebrowser.misc import guiprocess
    model = completionmodel.CompletionModel(column_widths=(10, 10, 80))
    for what, processes in itertools.groupby(
            (p for p in guiprocess.all_processes.values() if p is not None),
            lambda proc: proc.what):

        # put successful processes last
        sorted_processes = sorted(
            processes,
            key=lambda proc: proc.outcome.state_str() == 'successful',
        )

        entries = [(str(proc.pid), proc.outcome.state_str(), str(proc))
                   for proc in sorted_processes]
        cat = listcategory.ListCategory(what.capitalize(), entries, sort=False)
        model.add_category(cat)
    return model
