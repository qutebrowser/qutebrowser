from abc import ABCMeta, ABC, abstractmethod
from typing import Self
from qutebrowser.browser.browsertab import AbstractTab
from qutebrowser.mainwindow.statusbar.backforward import Backforward
from qutebrowser.mainwindow.statusbar.clock import Clock
from qutebrowser.mainwindow.statusbar.keystring import KeyString
from qutebrowser.mainwindow.statusbar.percentage import Percentage
from qutebrowser.mainwindow.statusbar.progress import Progress
from qutebrowser.mainwindow.statusbar.searchmatch import SearchMatch
from qutebrowser.mainwindow.statusbar.tabindex import TabIndex
from qutebrowser.mainwindow.statusbar.textbase import TextBase
from qutebrowser.qt.widgets import QWidget


class QABCMeta(ABCMeta, type(QWidget)):
    """Meta class that combines ABC and the Qt meta class"""
    pass


class StatusBarWidget(ABC, metaclass=QABCMeta):
    """Abstract base class for all status bar widgets"""

    @classmethod
    def from_config(cls, segment: str, tab: AbstractTab | None = None) -> Self:
        if segment == 'scroll_raw':
            widget = Percentage()
            widget.set_raw()

        elif segment.startswith('text:'):
            widget = TextBase()
            widget.setText(segment.split(':', maxsplit=1)[1])

        elif segment.startswith('clock:') or segment == 'clock':
            widget = Clock()
            split_segment = segment.split(':', maxsplit=1)
            if len(split_segment) == 2 and split_segment[1]:
                widget.format = split_segment[1]
            else:
                widget.format = '%X'

        elif segment == 'history':
            widget = Backforward()
            if tab:
                widget.on_tab_changed(tab)

        elif segment == 'progress':
            widget = Progress()
            if tab:
                widget.on_tab_changed(tab)

        elif segment == 'scroll':
            widget = Percentage()

        elif segment == 'tabs':
            widget = TabIndex()

        elif segment == 'keypress':
            widget = KeyString()

        elif segment == 'search_match':
            widget = SearchMatch()

        else:
            raise ValueError(f"unknown config widget: {segment}")

        return widget

    @abstractmethod
    def enable(self):
        pass

    @abstractmethod
    def disable(self):
        pass
