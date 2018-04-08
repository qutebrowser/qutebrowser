# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


def url(*, info):
    """A model which combines bookmarks and web history URLs.

    Used for the `open` command.
    """
    model = completionmodel.CompletionModel(column_widths=(40, 50, 10))

    bookmarks = [(m.url, m.title, ' '.join(m.tags)) for m in
                 objreg.get('bookmark-manager')]

    if bookmarks:
        model.add_category(listcategory.ListCategory(
            'Bookmarks', bookmarks, delete_func=_delete_bookmark, sort=False))

    if info.config.get('completion.web_history_max_items') != 0:
        hist_cat = histcategory.HistoryCategory(delete_func=_delete_history)
        model.add_category(hist_cat)
    return model


def bookmark(*, info=None):  # pylint: disable=unused-argument
    """A CompletionModel filled with all bookmarks."""
    model = completionmodel.CompletionModel(column_widths=(30, 50, 20))
    marks = ((m.url, m.title, ' '.join(m.tags))
             for m in objreg.get('bookmark-manager'))
    model.add_category(listcategory.ListCategory('Bookmarks', marks,
                                                 delete_func=_delete_bookmark,
                                                 sort=False))
    return model


def bookmark_tag(*args, info=None):  # pylint: disable=unused-argument
    """A CompletionModel filled with all bookmark tags."""
    model = completionmodel.CompletionModel(column_widths=(20, 80, 0))
    bookmarks = objreg.get('bookmark-manager')
    tags = ((t, '') for t in bookmarks.all_tags() if t not in args)
    cat = listcategory.ListCategory('Tags', tags)
    model.add_category(cat)
    return model
