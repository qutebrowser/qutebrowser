# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""CompletionModels for URLs."""

import datetime

from PyQt5.QtCore import pyqtSlot, Qt

from qutebrowser.utils import objreg, utils, qtutils, log
from qutebrowser.completion.models import sql
from qutebrowser.config import config


class UrlCompletionModel(sql.SqlCompletionModel):

    """A model which combines bookmarks, quickmarks and web history URLs.

    Used for the `open` command.
    """

    URL_COLUMN = 0
    TEXT_COLUMN = 1
    TIME_COLUMN = 2

    COLUMN_WIDTHS = (40, 50, 10)
    DUMB_SORT = Qt.DescendingOrder

    def __init__(self, parent=None):
        super().__init__(parent)

        self.columns_to_filter = [self.URL_COLUMN, self.TEXT_COLUMN]

        self._quickmark_cat = self.new_category("Quickmarks",
                                                primary_key='desc')
        self._bookmark_cat = self.new_category("Bookmarks")
        self._history_cat = self.new_category("History", sort_by='sort',
                                              sort_order=Qt.DescendingOrder)

        quickmark_manager = objreg.get('quickmark-manager')
        quickmarks = quickmark_manager.marks.items()
        for qm_name, qm_url in quickmarks:
            self._quickmark_cat.new_item(qm_url, qm_name)
        quickmark_manager.added.connect(
            lambda name, url: self._quickmark_cat.new_item(url, name))
        quickmark_manager.removed.connect(self.on_quickmark_removed)

        bookmark_manager = objreg.get('bookmark-manager')
        bookmarks = bookmark_manager.marks.items()
        for bm_url, bm_title in bookmarks:
            self._bookmark_cat.new_item(bm_url, bm_title)
        bookmark_manager.added.connect(
            lambda name, url: self._bookmark_cat.new_item(url, name))
        bookmark_manager.removed.connect(self.on_bookmark_removed)

        self._history = objreg.get('web-history')
        self._max_history = config.get('completion', 'web-history-max-items')
        history = utils.newest_slice(self._history, self._max_history)
        for entry in history:
            if not entry.redirect:
                self._history_cat.new_item(entry.url.toDisplayString(),
                                           entry.title,
                                           self._fmt_atime(entry.atime),
                                           sort=int(entry.atime))
        self._history.add_completion_item.connect(self.on_history_item_added)
        self._history.cleared.connect(self.on_history_cleared)

        objreg.get('config').changed.connect(self.reformat_timestamps)

    def _fmt_atime(self, atime):
        """Format an atime to a human-readable string."""
        fmt = config.get('completion', 'timestamp-format')
        if fmt is None:
            return ''
        try:
            dt = datetime.datetime.fromtimestamp(atime)
        except (ValueError, OSError, OverflowError):
            # Different errors which can occur for too large values...
            log.misc.error("Got invalid timestamp {}!".format(atime))
            return '(invalid)'
        else:
            return dt.strftime(fmt)

    @config.change_filter('completion', 'timestamp-format')
    def reformat_timestamps(self):
        """Reformat the timestamps if the config option was changed."""
        for i in range(self._history_cat.rowCount()):
            url_item = self._history_cat.child(i, self.URL_COLUMN)
            atime_item = self._history_cat.child(i, self.TIME_COLUMN)
            atime = url_item.data(sql.Role.sort)
            atime_item.setText(self._fmt_atime(atime))

    @pyqtSlot(object)
    def on_history_item_added(self, entry):
        """Slot called when a new history item was added."""
        if (self._max_history != -1 and
                self._history_cat.rowCount() > self._max_history):
            # TODO: just use sql's LIMIT on select
            self._history_cat.removeRow(0)
        # If the url already exists, replace it to update access time
        try:
            self._history_cat.remove_item(entry.url.toDisplayString())
        except KeyError:
            pass
        self._history_cat.new_item(entry.url.toDisplayString(),
                                   entry.title,
                                   self._fmt_atime(entry.atime),
                                   sort=int(entry.atime))

    @pyqtSlot()
    def on_history_cleared(self):
        # TODO: this might break if a filter is set
        self._history_cat.removeRows(0, self._history_cat.rowCount())

    @pyqtSlot(str)
    def on_quickmark_removed(self, name):
        """Called when a quickmark has been removed by the user.

        Args:
            name: The name of the quickmark which has been removed.
        """
        self._quickmark_cat.remove_item(name)

    @pyqtSlot(str)
    def on_bookmark_removed(self, url):
        """Called when a bookmark has been removed by the user.

        Args:
            url: The url of the bookmark which has been removed.
        """
        self._bookmark_cat.remove_item(url)

    def delete_cur_item(self, completion):
        """Delete the selected item.

        Args:
            completion: The Completion object to use.
        """
        index = completion.currentIndex()
        qtutils.ensure_valid(index)
        category = index.parent()
        index = category.child(index.row(), self.URL_COLUMN)
        url = index.data()
        qtutils.ensure_valid(category)

        if category.data() == 'Bookmarks':
            bookmark_manager = objreg.get('bookmark-manager')
            bookmark_manager.delete(url)
        elif category.data() == 'Quickmarks':
            quickmark_manager = objreg.get('quickmark-manager')
            sibling = index.sibling(index.row(), self.TEXT_COLUMN)
            qtutils.ensure_valid(sibling)
            name = sibling.data()
            quickmark_manager.delete(name)
