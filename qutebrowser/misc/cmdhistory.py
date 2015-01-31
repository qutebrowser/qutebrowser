# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Command history for the status bar."""

from PyQt5.QtCore import pyqtSlot, pyqtSignal, QObject

from qutebrowser.config import config
from qutebrowser.utils import usertypes, log


class HistoryEmptyError(Exception):

    """Raised when the history is empty."""

    pass


class HistoryEndReachedError(Exception):

    """Raised when the end of the history is reached."""

    pass


class History(QObject):

    """Command history.

    Attributes:
        handle_private_mode: Whether to ignore history in private mode.
        history: A list of executed commands, with newer commands at the end.
        _tmphist: Temporary history for history browsing (as NeighborList)

    Signals:
        changed: Emitted when an entry was added to the history.
    """

    changed = pyqtSignal()

    def __init__(self, history=None, parent=None):
        """Constructor.

        Args:
            history: The initial history to set.
        """
        super().__init__(parent)
        self.handle_private_mode = False
        self._tmphist = None
        if history is None:
            self.history = []
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
            items = [e for e in self.history if e.startswith(text)]
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
        try:
            return self._tmphist.nextitem()
        except IndexError:
            raise HistoryEndReachedError

    def append(self, text):
        """Append a new item to the history.

        Args:
            text: The text to append.
        """
        if (self.handle_private_mode and
                config.get('general', 'private-browsing')):
            return
        if not self.history or text != self.history[-1]:
            self.history.append(text)
            self.changed.emit()
