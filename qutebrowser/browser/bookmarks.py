# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# Copyright 2015 Antoni Boucher <bouanto@zoho.com>
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

import os.path
import functools
import collections

from PyQt5.QtCore import pyqtSignal, QUrl, QObject

from qutebrowser.utils import message, usertypes, urlutils, standarddir, objreg
from qutebrowser.commands import cmdexc, cmdutils
from qutebrowser.misc import lineparser


class BookmarkManager(QObject):

    """Manager for bookmarks.

    Attributes:
        marks: An OrderedDict of all bookmarks.
        _lineparser: The LineParser used for the bookmarks, or None
                     (when qutebrowser is started with -c '').

    Signals:
        changed: Emitted when anything changed.
        added: Emitted when a new bookmark was added.
               arg 0: The name of the bookmark.
               arg 1: The URL of the bookmark, as string.
        removed: Emitted when an existing bookmark was removed.
                 arg 0: The name of the bookmark.
    """

    changed = pyqtSignal()
    added = pyqtSignal(str, str)
    removed = pyqtSignal(str)

    def __init__(self, parent=None):
        """Initialize and read bookmarks."""
        super().__init__(parent)

        self.marks = collections.OrderedDict()

        if standarddir.config() is None:
            self._lineparser = None
        else:
            self._lineparser = lineparser.LineParser(
                standarddir.config(), 'bookmarks', parent=self)
            for line in self._lineparser:
                if not line.strip():
                    # Ignore empty or whitespace-only lines.
                    continue
                try:
                    key, url = line.rsplit(maxsplit=1)
                except ValueError:
                    message.error(0, "Invalid bookmark '{}'".format(line))
                else:
                    self.marks[key] = url
            filename = os.path.join(standarddir.config(), 'bookmarks')
            objreg.get('save-manager').add_saveable(
                'bookmark-manager', self.save, self.changed,
                filename=filename)

    def save(self):
        """Save the bookmarks to disk."""
        if self._lineparser is not None:
            self._lineparser.data = [' '.join(tpl)
                                     for tpl in self.marks.items()]
            self._lineparser.save()

    @cmdutils.register(instance='bookmark-manager', win_id='win_id')
    def bookmark_add(self, win_id, url, name):
        """Add a new bookmark.

        Args:
            win_id: The window ID to display the errors in.
            url: The url to add as bookmark.
            name: The name for the new bookmark.
        """
        if not url.isValid():
            urlutils.invalid_url_error(win_id, url, "save quickmark")
            return
        urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)

        # We don't raise cmdexc.CommandError here as this can be called async
        # via prompt_save.
        if not name:
            message.error(win_id, "Can't set mark with empty name!")
            return
        if not urlstr:
            message.error(win_id, "Can't set mark with empty URL!")
            return

        self.marks[name] = urlstr
        self.changed.emit()
        self.added.emit(name, urlstr)
        message.info(win_id, "Bookmarks added")

    @cmdutils.register(instance='bookmark-manager', maxsplit=0,
                       completion=[usertypes.Completion.bookmark_by_name])
    def bookmark_del(self, name):
        """Delete a bookmark.

        Args:
            name: The name of the bookmark to delete.
        """
        try:
            del self.marks[name]
        except KeyError:
            raise cmdexc.CommandError("Bookmark '{}' not found!".format(name))
        else:
            self.changed.emit()
            self.removed.emit(name)
