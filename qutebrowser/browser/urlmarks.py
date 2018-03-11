# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2015-2018 Antoni Boucher <bouanto@zoho.com>
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

"""Manager for bookmarks.

Note we violate our general QUrl rule by storing url strings in the marks
OrderedDict. This is because we read them from a file at start and write them
to a file on shutdown, so it makes sense to keep them as strings here.
"""

import os
import os.path
import collections
import json

from PyQt5.QtCore import pyqtSignal, QUrl, QObject

from qutebrowser.utils import urlutils, standarddir, objreg
from qutebrowser.misc import lineparser


class Error(Exception):

    """Base class for all errors in this module."""

    pass


class InvalidUrlError(Error):

    """Exception emitted when a URL is invalid."""

    pass


class DoesNotExistError(Error):

    """Exception emitted when a given URL does not exist."""

    pass


class AlreadyExistsError(Error):

    """Exception emitted when a given URL does already exist."""

    pass


Bookmark = collections.namedtuple('Bookmark', ['url', 'title', 'tags'])


class BookmarkManager(QObject):

    """Manager for bookmarks.

    Signals:
        changed: Emitted when a bookmark is added, removed, or modified.
    """

    changed = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize and read bookmarks."""
        super().__init__(parent)

        self._marks = collections.OrderedDict()
        self._init_lineparser()

        for line in self._lineparser:
            if not line.strip():
                # Ignore empty or whitespace-only lines.
                continue
            data = json.loads(line)
            mark = Bookmark(
                url=data['url'],
                title=data.get('title', ''),
                tags=data.get('tags', []),
            )
            self._marks[mark.url] = mark
        self._init_savemanager(objreg.get('save-manager'))

    def __iter__(self):
        return iter(self._marks.values())

    def __contains__(self, url):
        return url in self._marks

    def _init_lineparser(self):
        bookmarks_directory = os.path.join(standarddir.config(), 'bookmarks')
        if not os.path.isdir(bookmarks_directory):
            os.makedirs(bookmarks_directory)

        bookmarks_subdir = os.path.join('bookmarks', 'urls')
        self._lineparser = lineparser.LineParser(
            standarddir.config(), bookmarks_subdir, parent=self)

    def _init_savemanager(self, save_manager):
        filename = os.path.join(standarddir.config(), 'bookmarks', 'urls')
        save_manager.add_saveable('bookmark-manager', self.save, self.changed,
                                  filename=filename)

    def add(self, url, title, tags, *, toggle=False):
        """Add a new bookmark.

        Args:
            url: The url to add as bookmark.
            title: The title for the new bookmark.
            tags: The tags for the new bookmark.
            toggle: remove the bookmark instead of raising an error if it
                    already exists.

        Return:
            True if the bookmark was added, and False if it was
            removed (only possible if toggle is True).
        """
        if not url.isValid():
            errstr = urlutils.get_errstring(url)
            raise InvalidUrlError(errstr)

        urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)

        if urlstr in self._marks:
            if toggle:
                self.delete(urlstr)
                return False
            else:
                raise AlreadyExistsError("Bookmark already exists!")
        else:
            self._marks[urlstr] = Bookmark(urlstr, title or '', tags or [])
            self.changed.emit()
            return True

    def save(self):
        """Save the marks to disk."""
        self._lineparser.data = [json.dumps(m._asdict()) for m in self]
        self._lineparser.save()

    def get(self, url):
        urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
        return self._marks.get(urlstr)

    def update(self, mark):
        self._marks[mark.url] = mark
        self.changed.emit()

    def delete(self, key):
        """Delete a bookmark.

        Args:
            key: The url of the bookmark to delete.
        """
        del self._marks[key]
        self.changed.emit()
