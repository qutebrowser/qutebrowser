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

"""Classes that return miscellaneous completion models."""

import datetime
from typing import List, Sequence, Tuple, Optional
from abc import ABC, abstractmethod

from qutebrowser.config import config, configdata
from qutebrowser.utils import objreg, log, utils
from qutebrowser.completion.categories import listcategory
from qutebrowser.completion import completionmodel, util
from qutebrowser.browser import inspector
from qutebrowser.completion.completer import CompletionInfo
from qutebrowser.completion.strategies.strategy import CompletionStrategy
from qutebrowser.completion.completionmodel import CompletionModel


class Command(CompletionStrategy):

    """A CompletionModel filled with non-hidden commands and descriptions."""

    COLUMN_WIDTHS = (20, 60, 20)

    def populate(self, *args: str, info: CompletionInfo) -> CompletionModel:
        super().populate(*args, info=info)
        cmdlist = util.get_cmd_completions(info, include_aliases=True,
                                           include_hidden=False)
        self.model.add_category(listcategory.ListCategory("Commands", cmdlist))
        return self.model


class HelpTopic(CompletionStrategy):

    """A CompletionModel filled with help topics."""

    def populate(self, *args: str, info: CompletionInfo) -> CompletionModel:
        super().populate(*args, info=info)
        cmdlist = util.get_cmd_completions(info, include_aliases=False,
                                           include_hidden=True, prefix=':')
        settings = ((opt.name, opt.description, info.config.get_str(opt.name))
                    for opt in configdata.DATA.values())

        self.model.add_category(listcategory.ListCategory("Commands", cmdlist))
        self.model.add_category(listcategory.ListCategory("Settings", settings))
        return self.model


class QuickMark(CompletionStrategy):

    """A CompletionModel filled with all quickmarks."""

    COLUMN_WIDTHS = (30, 70, 0)

    def populate(self, *args: str, info: Optional[CompletionInfo]) -> CompletionModel:
        super().populate(*args, info=info)
        utils.unused(info)
        marks = objreg.get('quickmark-manager').marks.items()
        self.model.add_category(listcategory.ListCategory('Quickmarks', marks,
                                                     delete_func=self.delete,
                                                     sort=False))
        return self.model

    @classmethod
    def delete(cls, data: Sequence[str]) -> None:
        """Delete a quickmark from the completion menu."""
        name = data[0]
        quickmark_manager = objreg.get('quickmark-manager')
        log.completion.debug('Deleting quickmark {}'.format(name))
        quickmark_manager.delete(name)


class BookMark(CompletionStrategy):

    """A CompletionModel filled with all bookmarks."""

    COLUMN_WIDTHS = (30, 70, 0)

    def populate(self, *args: str, info: Optional[CompletionInfo]) -> CompletionModel:
        super().populate(*args, info=info)
        utils.unused(info)
        marks = objreg.get('bookmark-manager').marks.items()
        self.model.add_category(listcategory.ListCategory('Bookmarks', marks,
                                                     delete_func=self.delete,
                                                     sort=False))
        return self.model

    @classmethod
    def delete(cls, data: Sequence[str]) -> None:
        """Delete a bookmark from the completion menu."""
        urlstr = data[0]
        log.completion.debug('Deleting bookmark {}'.format(urlstr))
        bookmark_manager = objreg.get('bookmark-manager')
        bookmark_manager.delete(urlstr)


class Session(CompletionStrategy):

    """A CompletionModel filled with session names."""

    COLUMN_WIDTHS = (30, 70, 0)

    def populate(self, *args: str, info: Optional[CompletionInfo]) -> CompletionModel:
        from qutebrowser.misc import sessions

        super().populate(*args, info=info)
        utils.unused(info)
        try:
            sess = ((name,) for name
                    in sessions.session_manager.list_sessions()
                    if not name.startswith('_'))
            self.model.add_category(listcategory.ListCategory("Sessions", sess))
        except OSError:
            log.completion.exception("Failed to list sessions!")

        return self.model


class TabMaker(CompletionStrategy):
    """Helper to get the completion model for tabs/other_tabs."""
    COLUMN_WIDTHS = (6, 40, 46, 8)

    """
    Args:
        win_id_filter: A filter function for window IDs to include.
                       Should return True for all included windows.
        add_win_id: Whether to add the window ID to the completion items.
    """
    def __init__(self, win_id_filter=lambda _win_id: True, add_win_id=True):
        super().__init__()
        self.win_id_filter = win_id_filter
        self.add_win_id = add_win_id

    def populate(self, *args: str, info: Optional[CompletionInfo]) -> Optional[CompletionModel]:
        super().populate(*args, info=info)
        tabs_are_windows = config.val.tabs.tabs_are_windows
        # list storing all single-tabbed windows when tabs_are_windows
        windows: List[Tuple[str, str, str, str]] = []

        for win_id in objreg.window_registry:
            if not self.win_id_filter(win_id):
                continue

            tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                        window=win_id)
            if tabbed_browser.is_shutting_down:
                continue
            tab_entries: List[Tuple[str, str, str, str]] = []
            for idx in range(tabbed_browser.widget.count()):
                tab = tabbed_browser.widget.widget(idx)
                tab_str = ("{}/{}".format(win_id, idx + 1) if self.add_win_id
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
                title = str(win_id) if self.add_win_id else "Tabs"
                cat = listcategory.ListCategory(
                    title, tab_entries, delete_func=self.delete, sort=False)
                self.model.add_category(cat)

        if tabs_are_windows:
            win = listcategory.ListCategory(
                "Windows", windows, delete_func=self.delete, sort=False)
            self.model.add_category(win)

        return self.model

    @classmethod
    def delete(cls, data):
        """Close the selected tab."""
        win_id, tab_index = data[0].split('/')
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=int(win_id))
        tabbed_browser.on_tab_close_requested(int(tab_index) - 1)


class Tabs(TabMaker):
    """A model to complete on open tabs across all windows.

    Used for the tab-select command (and others).
    """
    def populate(self, *args: str, info: Optional[CompletionInfo] = None) -> Optional[CompletionModel]:
        utils.unused(info)
        return super().populate(*args, info=info)


class OtherTabs(TabMaker):
    """A model to complete on open tabs across all windows except the current.

    Used for the tab-take command.
    """

    def populate(self, *args: str, info: Optional[CompletionInfo] = None) -> Optional[CompletionModel]:
        self.win_id_filter = lambda win_id: win_id != info.win_id
        return super().populate(*args, info=info)


class TabFocus(TabMaker):
    """A model to complete on open tabs in the current window."""
    def populate(self, *args: str, info: Optional[CompletionInfo] = None) -> Optional[CompletionModel]:
        self.win_id_filter = lambda win_id: win_id == info.win_id
        self.add_win_id = False
        super().populate(*args, info=info)
        special = [
            ("last", "Focus the last-focused tab"),
            ("stack-next", "Go forward through a stack of focused tabs"),
            ("stack-prev", "Go backward through a stack of focused tabs"),
        ]
        self.model.add_category(listcategory.ListCategory("Special", special))

        return self.model


class Window(CompletionStrategy):
    """A model to complete on all open windows."""
    COLUMN_WIDTHS = (6, 30, 64)

    def populate(self, *args: str, info: Optional[CompletionInfo]) -> Optional[CompletionModel]:
        super().populate(*args, info=info)
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

        self.model.add_category(listcategory.ListCategory("Windows", windows))

        return self.model


class InspectorPosition(CompletionStrategy):
    """A model for possible inspector positions."""
    COLUMN_WIDTHS = (100, 0, 0)

    def populate(self, *args: str, info: Optional[CompletionInfo]) -> Optional[CompletionModel]:
        super().populate(*args, info=info)
        utils.unused(info)
        positions = [(e.name,) for e in inspector.Position]
        category = listcategory.ListCategory("Position (optional)", positions)
        self.model.add_category(category)
        return self.model


def _qdatetime_to_completion_format(qdate):
    if not qdate.isValid():
        ts = 0
    else:
        ts = qdate.toMSecsSinceEpoch()
        if ts < 0:
            ts = 0
    pydate = datetime.datetime.fromtimestamp(ts / 1000)
    return pydate.strftime(config.val.completion.timestamp_format)


class HistoryStrategy(CompletionStrategy):
    COLUMN_WIDTHS = (5, 36, 50, 9)

    def __init__(self, go_forward: bool):
        super().__init__()
        self.go_forward = go_forward

    def populate(self, *args: str, info: Optional[CompletionInfo]) -> Optional[CompletionModel]:
        super().populate(*args, info=info)
        history = info.cur_tab.history
        current_idx = history.current_idx()

        if self.go_forward:
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
        if not self.go_forward:
            # make sure the most recent is at the top for :back
            entries.reverse()

        cat = listcategory.ListCategory("History", entries, sort=False)
        self.model.add_category(cat)
        return self.model


class Forward(HistoryStrategy):
    """A model to complete on history of the current tab.

    Used for the :forward command.
    """
    def __init__(self):
        super().__init__(True)


class Back(HistoryStrategy):
    """A model to complete on history of the current tab.

    Used for the :back command.
    """
    def __init__(self):
        super().__init__(False)


class Undo(CompletionStrategy):
    """A model to complete undo entries."""
    COLUMN_WIDTHS = (6, 84, 10)

    def populate(self, *args: str, info: Optional[CompletionInfo]) -> Optional[CompletionModel]:
        super().populate(*args, info=info)
        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=info.win_id)
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
        self.model.add_category(cat)
        return self.model
