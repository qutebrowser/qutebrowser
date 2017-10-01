# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""A completion category that queries the SQL History store."""

import re

from PyQt5.QtSql import QSqlQueryModel

from qutebrowser.misc import sql
from qutebrowser.utils import debug
from qutebrowser.config import config


class HistoryCategory(QSqlQueryModel):

    """A completion category that queries the SQL History store."""

    def __init__(self, *, delete_func=None, parent=None):
        """Create a new History completion category."""
        super().__init__(parent=parent)
        self.name = "History"

        # replace ' in timestamp-format to avoid breaking the query
        timestamp_format = config.val.completion.timestamp_format
        timefmt = ("strftime('{}', last_atime, 'unixepoch', 'localtime')"
                   .format(timestamp_format.replace("'", "`")))

        self._query = sql.Query(' '.join([
            "SELECT url, title, {}".format(timefmt),
            "FROM CompletionHistory",
            # the incoming pattern will have literal % and _ escaped with '\'
            # we need to tell sql to treat '\' as an escape character
            "WHERE (url LIKE :pat escape '\\' or title LIKE :pat escape '\\')",
            self._atime_expr(),
            "ORDER BY last_atime DESC",
        ]), forward_only=False)

        # advertise that this model filters by URL and title
        self.columns_to_filter = [0, 1]
        self.delete_func = delete_func

    def _atime_expr(self):
        """If max_items is set, return an expression to limit the query."""
        max_items = config.val.completion.web_history_max_items
        # HistoryCategory should not be added to the completion in that case.
        assert max_items != 0

        if max_items < 0:
            return ''

        min_atime = sql.Query(' '.join([
            'SELECT min(last_atime) FROM',
            '(SELECT last_atime FROM CompletionHistory',
            'ORDER BY last_atime DESC LIMIT :limit)',
        ])).run(limit=max_items).value()

        if not min_atime:
            # if there are no history items, min_atime may be '' (issue #2849)
            return ''

        return "AND last_atime >= {}".format(min_atime)

    def set_pattern(self, pattern):
        """Set the pattern used to filter results.

        Args:
            pattern: string pattern to filter by.
        """
        # escape to treat a user input % or _ as a literal, not a wildcard
        pattern = pattern.replace('%', '\\%')
        pattern = pattern.replace('_', '\\_')
        # treat spaces as wildcards to match any of the typed words
        pattern = re.sub(r' +', '%', pattern)
        pattern = '%{}%'.format(pattern)
        with debug.log_time('sql', 'Running completion query'):
            self._query.run(pat=pattern)
        self.setQuery(self._query)

    def removeRows(self, row, _count, _parent=None):
        """Override QAbstractItemModel::removeRows to re-run sql query."""
        # re-run query to reload updated table
        with debug.log_time('sql', 'Re-running completion query post-delete'):
            self._query.run()
        self.setQuery(self._query)
        while self.rowCount() < row:
            self.fetchMore()
        return True
