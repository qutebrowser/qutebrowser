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

Note we violate our general QUrl rule by storing url strings in the bookmarks
OrderedDict. This is because we read them from a file at start and write them
to a file on shutdown, so it makes sense to keep them as strings here.
"""

import os
import os.path

from PyQt5.QtCore import QUrl

from qutebrowser.utils import message, standarddir
from qutebrowser.misc import lineparser
from qutebrowser.browser.urlmark import UrlMarkManager


class BookmarkManager(UrlMarkManager):

    """Manager for bookmarks.

    The primary key for bookmarks is their *url*, this means:

        - self.marks maps URLs to titles.
        - changed gets emitted with the URL as first argument and the title as
          second argument.
        - removed gets emitted with the URL as argument.
    """

    def _init_lineparser(self):
        bookmarks_directory = os.path.join(standarddir.config(), 'bookmarks')
        if not os.path.isdir(bookmarks_directory):
            os.makedirs(bookmarks_directory)
        self._lineparser = lineparser.LineParser(
            standarddir.config(), 'bookmarks/urls', parent=self)

    def _init_savemanager(self, save_manager):
        filename = os.path.join(standarddir.config(), 'bookmarks/urls')
        save_manager.add_saveable('bookmark-manager', self.save, self.changed,
                                  filename=filename)

    def _parse_line(self, line):
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            self.marks[parts[0]] = parts[1]
        elif len(parts) == 1:
            self.marks[parts[0]] = ''

    def add(self, win_id, url, title):
        """Add a new bookmark.

        Args:
            win_id: The window ID to display the errors in.
            url: The url to add as bookmark.
            title: The title for the new bookmark.
        """
        urlstr = url.toString(QUrl.RemovePassword | QUrl.FullyEncoded)

        if urlstr in self.marks:
            message.error(win_id, "Bookmark already exists!")
        else:
            self.marks[urlstr] = title
            self.changed.emit()
            self.added.emit(title, urlstr)
            message.info(win_id, "Bookmark added")
