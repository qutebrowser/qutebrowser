# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Simple history which gets written to disk."""

import time
import functools

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWebKit import QWebHistoryInterface

from qutebrowser.utils import utils, objreg, standarddir
from qutebrowser.config import config
from qutebrowser.config.parsers import line as lineparser


class HistoryEntry:

    """A single entry in the web history.

    Attributes:
        atime: The time the page was accessed.
        url: The URL which was accessed as string
    """

    def __init__(self, atime, url):
        self.atime = atime
        self.url = url

    def __repr__(self):
        return utils.get_repr(self, constructor=True, atime=self.atime,
                              url=self.url)

    def __str__(self):
        return '{} {}'.format(int(self.atime), self.url)

    @classmethod
    def from_str(cls, s):
        """Get a history based on a 'TIME URL' string."""
        return cls(*s.split(' ', maxsplit=1))


class WebHistory(QWebHistoryInterface):

    """A QWebHistoryInterface which supports being written to disk."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._linecp = lineparser.LineConfigParser(standarddir.data, 'history',
                                                   parent=self)
        self._history = [HistoryEntry.from_str(e) for e in self._linecp.data]
        objreg.get('save-manager').add_saveable('history', self.save,
                                                self.changed)

    def __repr__(self):
        return utils.get_repr(self, length=len(self._history))

    def __getitem__(self, key):
        return self._history[key]

    def save(self):
        """Save the history to disk."""
        self._linecp.data = (str(e) for e in self._history)
        self._linecp.save()

    def addHistoryEntry(self, url_string):
        """Called by WebKit when an URL should be added to the history.

        Args:
            url_string: An url as string to add to the history.
        """
        if not config.get('general', 'private-browsing'):
            entry = HistoryEntry(time.time(), url_string)
            self._history.append(entry)
            self.historyContains.cache_clear()
            self.changed.emit()

    @functools.lru_cache()
    def historyContains(self, url_string):
        """Called by WebKit to determine if an URL is contained in the history.

        Args:
            url_string: The URL (as string) to check for.

        Return:
            True if the url is in the history, False otherwise.
        """
        return url_string in (entry.url for entry in self._history)


def init():
    """Initialize the web history."""
    history = WebHistory()
    objreg.register('web-history', history)
    QWebHistoryInterface.setDefaultInterface(history)
