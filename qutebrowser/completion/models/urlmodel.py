# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Function to return the url completion model for the `open` command."""

import datetime

from PyQt5.QtCore import pyqtSlot, Qt

from qutebrowser.utils import objreg, utils, qtutils, log
from qutebrowser.completion.models import base
from qutebrowser.config import config

_URL_COLUMN = 0
_TEXT_COLUMN = 1
_TIME_COLUMN = 2
_model = None
_history_cat = None
_quickmark_cat = None
_bookmark_cat = None


def _delete_url(completion):
    index = completion.currentIndex()
    qtutils.ensure_valid(index)
    category = index.parent()
    index = category.child(index.row(), _URL_COLUMN)
    qtutils.ensure_valid(category)
    if category.data() == 'Bookmarks':
        bookmark_manager = objreg.get('bookmark-manager')
        bookmark_manager.delete(index.data())
    elif category.data() == 'Quickmarks':
        quickmark_manager = objreg.get('quickmark-manager')
        sibling = index.sibling(index.row(), _TEXT_COLUMN)
        qtutils.ensure_valid(sibling)
        name = sibling.data()
        quickmark_manager.delete(name)


def _remove_oldest_history():
    """Remove the oldest history entry."""
    _history_cat.removeRow(0)


def _add_history_entry(entry):
    """Add a new history entry to the completion."""
    _model.new_item(_history_cat, entry.url.toDisplayString(),
                    entry.title, _fmt_atime(entry.atime),
                    sort=int(entry.atime), userdata=entry.url)

    max_history = config.get('completion', 'web-history-max-items')
    if max_history != -1 and _history_cat.rowCount() > max_history:
        _remove_oldest_history()


@config.change_filter('completion', 'timestamp-format')
def _reformat_timestamps():
    """Reformat the timestamps if the config option was changed."""
    for i in range(_history_cat.rowCount()):
        url_item = _history_cat.child(i, _URL_COLUMN)
        atime_item = _history_cat.child(i, _TIME_COLUMN)
        atime = url_item.data(base.Role.sort)
        atime_item.setText(_fmt_atime(atime))


@pyqtSlot(object)
def _on_history_item_added(entry):
    """Slot called when a new history item was added."""
    for i in range(_history_cat.rowCount()):
        url_item = _history_cat.child(i, _URL_COLUMN)
        atime_item = _history_cat.child(i, _TIME_COLUMN)
        title_item = _history_cat.child(i, _TEXT_COLUMN)
        if url_item.data(base.Role.userdata) == entry.url:
            atime_item.setText(_fmt_atime(entry.atime))
            title_item.setText(entry.title)
            url_item.setData(int(entry.atime), base.Role.sort)
            break
    else:
        _add_history_entry(entry)


@pyqtSlot()
def _on_history_cleared():
    _history_cat.removeRows(0, _history_cat.rowCount())


def _remove_item(data, category, column):
    """Helper function for on_quickmark_removed and on_bookmark_removed.

    Args:
        data: The item to search for.
        category: The category to search in.
        column: The column to use for matching.
    """
    for i in range(category.rowCount()):
        item = category.child(i, column)
        if item.data(Qt.DisplayRole) == data:
            category.removeRow(i)
            break


@pyqtSlot(str)
def _on_quickmark_removed(name):
    """Called when a quickmark has been removed by the user.

    Args:
        name: The name of the quickmark which has been removed.
    """
    _remove_item(name, _quickmark_cat, _TEXT_COLUMN)


@pyqtSlot(str)
def _on_bookmark_removed(urltext):
    """Called when a bookmark has been removed by the user.

    Args:
        urltext: The url of the bookmark which has been removed.
    """
    _remove_item(urltext, _bookmark_cat, _URL_COLUMN)


def _fmt_atime(atime):
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


def _init():
    global _model, _quickmark_cat, _bookmark_cat, _history_cat
    _model = base.CompletionModel(column_widths=(40, 50, 10),
                                  dumb_sort=Qt.DescendingOrder,
                                  delete_cur_item=_delete_url,
                                  columns_to_filter=[_URL_COLUMN,
                                                     _TEXT_COLUMN])
    _quickmark_cat = _model.new_category("Quickmarks")
    _bookmark_cat = _model.new_category("Bookmarks")
    _history_cat = _model.new_category("History")

    quickmark_manager = objreg.get('quickmark-manager')
    quickmarks = quickmark_manager.marks.items()
    for qm_name, qm_url in quickmarks:
        _model.new_item(_quickmark_cat, qm_url, qm_name)
    quickmark_manager.added.connect(
        lambda name, url: _model.new_item(_quickmark_cat, url, name))
    quickmark_manager.removed.connect(_on_quickmark_removed)

    bookmark_manager = objreg.get('bookmark-manager')
    bookmarks = bookmark_manager.marks.items()
    for bm_url, bm_title in bookmarks:
        _model.new_item(_bookmark_cat, bm_url, bm_title)
    bookmark_manager.added.connect(
        lambda name, url: _model.new_item(_bookmark_cat, url, name))
    bookmark_manager.removed.connect(_on_bookmark_removed)

    history = objreg.get('web-history')
    max_history = config.get('completion', 'web-history-max-items')
    for entry in utils.newest_slice(history, max_history):
        if not entry.redirect:
            _add_history_entry(entry)
    history.add_completion_item.connect(_on_history_item_added)
    history.cleared.connect(_on_history_cleared)

    objreg.get('config').changed.connect(_reformat_timestamps)


def url():
    """A _model which combines bookmarks, quickmarks and web history URLs.

    Used for the `open` command.
    """
    if not _model:
        _init()
    return _model
