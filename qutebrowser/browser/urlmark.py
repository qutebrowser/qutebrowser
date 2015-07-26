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

"""Base manager for bookmarks and quickmarks.

Note we violate our general QUrl rule by storing url strings in the marks
OrderedDict. This is because we read them from a file at start and write them
to a file on shutdown, so it makes sense to keep them as strings here.
"""

import collections

from PyQt5.QtCore import pyqtSignal, QObject

from qutebrowser.utils import standarddir, objreg


class UrlMarkManager(QObject):

    """Base class for BookmarkManager and QuickmarkManager.

    Attributes:
        marks: An OrderedDict of all quickmarks/bookmarks.
        _lineparser: The LineParser used for the marks, or None
                     (when qutebrowser is started with -c '').

    Signals:
        changed: Emitted when anything changed.
        added: Emitted when a new quickmark/bookmark was added.
        removed: Emitted when an existing quickmark/bookmark was removed.
    """

    changed = pyqtSignal()
    added = pyqtSignal(str, str)
    removed = pyqtSignal(str)

    def __init__(self, parent=None):
        """Initialize and read quickmarks."""
        super().__init__(parent)

        self.marks = collections.OrderedDict()
        self._lineparser = None

        if standarddir.config() is None:
            return

        self._init_lineparser()
        for line in self._lineparser:
            if not line.strip():
                # Ignore empty or whitespace-only lines.
                continue
            self._parse_line(line)
        self._init_savemanager(objreg.get('save-manager'))

    def _init_lineparser(self):
        raise NotImplementedError

    def _parse_line(self, line):
        raise NotImplementedError

    def _init_savemanager(self, _save_manager):
        raise NotImplementedError

    def save(self):
        """Save the marks to disk."""
        if self._lineparser is not None:
            self._lineparser.data = [' '.join(tpl)
                                     for tpl in self.marks.items()]
            self._lineparser.save()

    def delete(self, key):
        """Delete a quickmark/bookmark.

        Args:
            key: The key to delete (name for quickmarks, URL for bookmarks.)
        """
        del self.marks[key]
        self.changed.emit()
        self.removed.emit(key)
