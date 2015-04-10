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
import collections

from PyQt5.QtCore import pyqtSignal, QUrl
from PyQt5.QtWebKit import QWebHistoryInterface

from qutebrowser.utils import utils, objreg, standarddir, log
from qutebrowser.config import config
from qutebrowser.misc import lineparser


class HistoryEntry:

    """A single entry in the web history.

    Attributes:
        atime: The time the page was accessed.
        url: The URL which was accessed as QUrl.
        url_string: The URL which was accessed as string.
    """

    def __init__(self, atime, url):
        self.atime = float(atime)
        self.url = QUrl(url)
        self.url_string = url

    def __repr__(self):
        return utils.get_repr(self, constructor=True, atime=self.atime,
                              url=self.url.toDisplayString())

    def __str__(self):
        return '{} {}'.format(int(self.atime), self.url_string)

    @classmethod
    def from_str(cls, s):
        """Get a history based on a 'TIME URL' string."""
        return cls(*s.split(' ', maxsplit=1))


class WebHistory(QWebHistoryInterface):

    """A QWebHistoryInterface which supports being written to disk.

    Attributes:
        _lineparser: The AppendLineParser used to save the history.
        _history_dict: An OrderedDict of URLs read from the on-disk history.
        _new_history: A list of HistoryEntry items of the current session.
        _saved_count: How many HistoryEntries have been written to disk.

    Signals:
        item_about_to_be_added: Emitted before a new HistoryEntry is added.
                                arg: The new HistoryEntry.
        item_added: Emitted after a new HistoryEntry is added.
                    arg: The new HistoryEntry.
    """

    item_about_to_be_added = pyqtSignal(HistoryEntry)
    item_added = pyqtSignal(HistoryEntry)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lineparser = lineparser.AppendLineParser(
            standarddir.data(), 'history', parent=self)
        self._history_dict = collections.OrderedDict()
        with self._lineparser.open():
            for line in self._lineparser:
                data = line.rstrip().split(maxsplit=1)
                if not data:
                    # empty line
                    continue
                elif len(data) != 2:
                    # other malformed line
                    log.init.warning("Invalid history entry {!r}!".format(
                        line))
                    continue
                atime, url = data
                # This de-duplicates history entries; only the latest
                # entry for each URL is kept. If you want to keep
                # information about previous hits change the items in
                # old_urls to be lists or change HistoryEntry to have a
                # list of atimes.
                self._history_dict[url] = HistoryEntry(atime, url)
                self._history_dict.move_to_end(url)
        self._new_history = []
        self._saved_count = 0
        objreg.get('save-manager').add_saveable(
            'history', self.save, self.item_added)

    def __repr__(self):
        return utils.get_repr(self, length=len(self))

    def __getitem__(self, key):
        return self._new_history[key]

    def __iter__(self):
        return iter(self._history_dict.values())

    def __len__(self):
        return len(self._history_dict)

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
        if not url_string:
            return
        if not config.get('general', 'private-browsing'):
            entry = HistoryEntry(time.time(), url_string)
            self.item_about_to_be_added.emit(entry)
            self._new_history.append(entry)
            self._history_dict[url_string] = entry
            self._history_dict.move_to_end(url_string)
            self.item_added.emit(entry)

    def historyContains(self, url_string):
        """Called by WebKit to determine if an URL is contained in the history.

        Args:
            url_string: The URL (as string) to check for.

        Return:
            True if the url is in the history, False otherwise.
        """
        return url_string in self._history_dict


def init(parent=None):
    """Initialize the web history.

    Args:
        parent: The parent to use for WebHistory.
    """
    history = WebHistory(parent)
    objreg.register('web-history', history)
    QWebHistoryInterface.setDefaultInterface(history)
