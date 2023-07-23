# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Command history for the status bar."""

from typing import MutableSequence

from qutebrowser.qt.core import pyqtSlot, pyqtSignal, QObject

from qutebrowser.utils import usertypes, log, standarddir, objreg
from qutebrowser.misc import lineparser


class HistoryEmptyError(Exception):

    """Raised when the history is empty."""


class HistoryEndReachedError(Exception):

    """Raised when the end of the history is reached."""


class History(QObject):

    """Command history.

    Attributes:
        history: A list of executed commands, with newer commands at the end.
        _tmphist: Temporary history for history browsing (as NeighborList)

    Signals:
        changed: Emitted when an entry was added to the history.
    """

    changed = pyqtSignal()

    def __init__(self, *, history=None, parent=None):
        """Constructor.

        Args:
            history: The initial history to set.
        """
        super().__init__(parent)
        self._tmphist = None
        if history is None:
            self.history: MutableSequence[str] = []
        else:
            self.history = history

    def __getitem__(self, idx):
        return self.history[idx]

    def is_browsing(self):
        """Check _tmphist to see if we're browsing."""
        return self._tmphist is not None

    def start(self, text):
        """Start browsing to the history.

        Called when the user presses the up/down key and wasn't browsing the
        history already.

        Args:
            text: The preset text.
        """
        log.misc.debug("Preset text: '{}'".format(text))
        if text:
            items: MutableSequence[str] = [
                e for e in self.history
                if e.startswith(text)]
        else:
            items = self.history
        if not items:
            raise HistoryEmptyError
        self._tmphist = usertypes.NeighborList(items)
        return self._tmphist.lastitem()

    @pyqtSlot()
    def stop(self):
        """Stop browsing the history."""
        self._tmphist = None

    def previtem(self):
        """Get the previous item in the temp history.

        start() needs to be called before calling this.
        """
        if not self.is_browsing():
            raise ValueError("Currently not browsing history")
        assert self._tmphist is not None

        try:
            return self._tmphist.previtem()
        except IndexError:
            raise HistoryEndReachedError

    def nextitem(self):
        """Get the next item in the temp history.

        start() needs to be called before calling this.
        """
        if not self.is_browsing():
            raise ValueError("Currently not browsing history")
        assert self._tmphist is not None

        try:
            return self._tmphist.nextitem()
        except IndexError:
            raise HistoryEndReachedError

    def append(self, text):
        """Append a new item to the history.

        Args:
            text: The text to append.
        """
        if not self.history or text != self.history[-1]:
            self.history.append(text)
            self.changed.emit()


def init():
    """Initialize the LimitLineParser storing the history."""
    save_manager = objreg.get('save-manager')
    command_history = lineparser.LimitLineParser(
        standarddir.data(), 'cmd-history',
        limit='completion.cmd_history_max_items')
    objreg.register('command-history', command_history)
    save_manager.add_saveable('command-history', command_history.save,
                              command_history.changed)
