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

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWebKit import QWebHistoryInterface

from qutebrowser.utils import utils, objreg, standarddir
from qutebrowser.config import config
from qutebrowser.misc import lineparser


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

    """A QWebHistoryInterface which supports being written to disk.

    Attributes:
        _lineparser: The AppendLineParser used to save the history.
        _old_urls: A set of URLs read from the on-disk history.
        _new_history: A list of HistoryEntry items of the current session.
        _saved_count: How many HistoryEntries have been written to disk.
        _old_hit: How many times an URL was found in _old_urls.
        _old_miss: How many times an URL was not found in _old_urls.
    """

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lineparser = lineparser.AppendLineParser(
            standarddir.data(), 'history', parent=self)
        self._old_urls = {}
        with self._lineparser.open():
            for line in self._lineparser:
                atime, url = line.rstrip().split(maxsplit=1)
                # This de-duplicates history entries. We keep later ones in the
                # file which usually the last ones accessed. If you want
                # to keep information about multiple hits change the
                # items in old_urls to be lists or change HistoryEntry
                # to have a list of atimes.
                self._old_urls[url] = HistoryEntry(atime, url)
        self._new_history = []
        self._saved_count = 0
        self._old_hit = 0
        self._old_miss = 0
        objreg.get('save-manager').add_saveable(
            'history', self.save, self.changed)

    def __repr__(self):
        return utils.get_repr(self, new_length=len(self._new_history))

    def __getitem__(self, key):
        return self._new_history[key]

    def __iter__(self):
        import itertools
        return itertools.chain(self._old_urls.values(), iter(self._new_history))

    def get_recent(self):
        """Get the most recent history entries."""
        old = self._lineparser.get_recent()
        return old + [str(e) for e in self._new_history]

    def save(self):
        """Save the history to disk."""
        new = (str(e) for e in self._new_history[self._saved_count:])
        self._lineparser.new_data = new
        self._lineparser.save()
        self._saved_count = len(self._new_history)

    def addHistoryEntry(self, url_string):
        """Called by WebKit when an URL should be added to the history.

        Args:
            url_string: An url as string to add to the history.
        """
        if not config.get('general', 'private-browsing'):
            entry = HistoryEntry(time.time(), url_string)
            self._new_history.append(entry)
            self.changed.emit()

    def historyContains(self, url_string):
        """Called by WebKit to determine if an URL is contained in the history.

        Args:
            url_string: The URL (as string) to check for.

        Return:
            True if the url is in the history, False otherwise.
        """
        if url_string in self._old_urls:
            self._old_hit += 1
            return True
        else:
            self._old_miss += 1
            return url_string in (entry.url for entry in self._new_history)


def init():
    """Initialize the web history."""
    history = WebHistory()
    objreg.register('web-history', history)
    QWebHistoryInterface.setDefaultInterface(history)
