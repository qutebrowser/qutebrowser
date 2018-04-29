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


class NotUniqueError(Error):

    """Exception emitted when a tag is not unique."""

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
        bookmarks_path = os.path.join(standarddir.config(), 'bookmarks.jsonl')
        self._lineparser = lineparser.LineParser(
            standarddir.config(), bookmarks_path, parent=self)

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

        save_manager = objreg.get('save-manager')
        save_manager.add_saveable('bookmark-manager', self.save, self.changed,
                                  filename=bookmarks_path)

    def __iter__(self):
        return iter(self._marks.values())

    def __contains__(self, url):
        return url in self._marks

    def add(self, url, title, *, toggle=False):
        """Add a new bookmark.

        Args:
            url: The url to add as bookmark.
            title: The title for the new bookmark.
            toggle: remove the bookmark instead of raising an error if it
                    already exists.

        Return:
            True if the bookmark was added, and False if it was
            removed (only possible if toggle is True).
        """
        if not url.isValid():
            errstr = urlutils.get_errstring(url)
            raise InvalidUrlError(errstr)

        urlstr = self._urlstr(url)

        if urlstr in self._marks:
            if toggle:
                self.delete(url)
                return False
            else:
                raise AlreadyExistsError("Bookmark already exists!")
        else:
            self._marks[urlstr] = Bookmark(urlstr, title or '', [])
            # place new marks at the end
            self._marks.move_to_end(urlstr, last=False)
            self.changed.emit()
            return True

    def save(self):
        """Save the marks to disk."""
        self._lineparser.data = [json.dumps(m._asdict()) for m in self]
        self._lineparser.save()

    def get(self, url):
        """Get a bookmark, or None if no such mark exists.

        Args:
            url: The QUrl of the mark to find.
        """
        urlstr = self._urlstr(url)
        mark = self._marks.get(urlstr)
        if not mark:
            raise DoesNotExistError("Bookmark '{}' not found!".format(urlstr))
        return mark

    def get_tagged(self, tags):
        """Get all bookmarks that have all the provided tags.

        Args:
            tags: List of tags to filter by.
        """
        return (m for m in self._marks.values()
                if all(t in m.tags for t in tags))

    def tag(self, url, tags, unique=False):
        """Add tags to a mark.

        Args:
            url: QUrl of the mark to modify.
            tags: List of tags to remove.
            unique: Raise NotUniqueError if one of the tags is already in use.
        """
        if unique:
            violations = [t for t in tags if any(self.get_tagged([t]))]
            if violations:
                raise NotUniqueError("{} are not unique".format(violations))
        mark = self.get(url)
        mark.tags.extend((t for t in tags if t not in mark.tags))
        self.changed.emit()

    def untag(self, url, tags, purge=False):
        """Remove tags from a mark.

        Args:
            url: QUrl of the mark to modify.
            tags: List of tags to remove.
            purge: Remove the mark if it has no tags left
        """
        mark = self.get(url)
        for t in tags:
            try:
                mark.tags.remove(t)
            except ValueError:
                pass
        if purge and not mark.tags:
            self.delete(url)
        self.changed.emit()

    def delete(self, key):
        """Delete a bookmark.

        Args:
            key: The QUrl of the bookmark to delete.
        """
        urlstr = self._urlstr(key)
        try:
            del self._marks[urlstr]
        except KeyError:
            raise DoesNotExistError("Bookmark '{}' not found!".format(urlstr))
        self.changed.emit()

    def all_tags(self):
        """Get the set of all defined tags."""
        tags = set()
        for m in self:
            tags = tags.union(m.tags)
        return tags

    def _urlstr(self, url):
        """Convert a QUrl into the string format used as a key."""
        if not url.isValid():
            raise InvalidUrlError(urlutils.get_errstring(url))
        return url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)
