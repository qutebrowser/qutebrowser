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

from qutebrowser.completion.models import (completionmodel, listcategory,
                                           histcategory)
from qutebrowser.utils import log, objreg


_URLCOL = 0
_TEXTCOL = 1


def _delete_history(data):
    urlstr = data[_URLCOL]
    log.completion.debug('Deleting history entry {}'.format(urlstr))
    hist = objreg.get('web-history')
    hist.delete_url(urlstr)


def _delete_bookmark(data):
    urlstr = data[_URLCOL]
    log.completion.debug('Deleting bookmark {}'.format(urlstr))
    bookmark_manager = objreg.get('bookmark-manager')
    bookmark_manager.delete(urlstr)


def _delete_quickmark(data):
    name = data[_TEXTCOL]
    quickmark_manager = objreg.get('quickmark-manager')
    log.completion.debug('Deleting quickmark {}'.format(name))
    quickmark_manager.delete(name)


def url(*, info):
    """A model which combines bookmarks, quickmarks and web history URLs.

    Used for the `open` command.
    """
    model = completionmodel.CompletionModel(column_widths=(40, 50, 10))

    quickmarks = ((url, name) for (name, url)
                  in objreg.get('quickmark-manager').marks.items())
    bookmarks = objreg.get('bookmark-manager').marks.items()

    model.add_category(listcategory.ListCategory(
        'Quickmarks', quickmarks, delete_func=_delete_quickmark, sort=False))
    model.add_category(listcategory.ListCategory(
        'Bookmarks', bookmarks, delete_func=_delete_bookmark, sort=False))

    if info.config.get('completion.web_history_max_items') != 0:
        hist_cat = histcategory.HistoryCategory(delete_func=_delete_history)
        model.add_category(hist_cat)
    return model
