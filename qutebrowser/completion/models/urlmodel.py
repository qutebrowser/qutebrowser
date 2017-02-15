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

from qutebrowser.completion.models import sqlmodel
from qutebrowser.config import config
from qutebrowser.utils import qtutils, log, objreg


_URLCOL = 0
_TEXTCOL = 1


def _delete_url(completion):
    """Delete the selected item.

    Args:
        completion: The Completion object to use.
    """
    index = completion.currentIndex()
    qtutils.ensure_valid(index)
    category = index.parent()
    index = category.child(index.row(), _URLCOL)
    catname = category.data()
    qtutils.ensure_valid(category)

    if catname == 'Bookmarks':
        urlstr = index.data()
        log.completion.debug('Deleting bookmark {}'.format(urlstr))
        bookmark_manager = objreg.get('bookmark-manager')
        bookmark_manager.delete(urlstr)
    else:
        assert catname == 'Quickmarks', 'Unknown category {}'.format(catname)
        quickmark_manager = objreg.get('quickmark-manager')
        sibling = index.sibling(index.row(), _TEXTCOL)
        qtutils.ensure_valid(sibling)
        name = sibling.data()
        log.completion.debug('Deleting quickmark {}'.format(name))
        quickmark_manager.delete(name)


def url():
    """A model which combines bookmarks, quickmarks and web history URLs.

    Used for the `open` command.
    """
    model = sqlmodel.SqlCompletionModel(column_widths=(40, 50, 10),
                                        columns_to_filter=[_URLCOL, _TEXTCOL],
                                        delete_cur_item=_delete_url)
    limit = config.get('completion', 'web-history-max-items')
    timefmt = config.get('completion', 'timestamp-format')
    select_time = "strftime('{}', atime, 'unixepoch')".format(timefmt)
    model.new_category('Quickmarks', select='url, name')
    model.new_category('Bookmarks')
    model.new_category('History',
                       limit=limit,
                       select='url, title, {}'.format(select_time),
                       where='not redirect')
    return model
