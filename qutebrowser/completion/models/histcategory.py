# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""A completion category that queries the SQL history store."""

import typing

from PyQt5.QtSql import QSqlQueryModel
from PyQt5.QtWidgets import QWidget

from qutebrowser.misc import sql
from qutebrowser.utils import debug, message, log
from qutebrowser.config import config
from qutebrowser.completion.models import util


class HistoryCategory(QSqlQueryModel):

    """A completion category that queries the SQL history store."""

    def __init__(self, *,
                 delete_func: util.DeleteFuncType = None,
                 parent: QWidget = None) -> None:
        """Create a new History completion category."""
        super().__init__(parent=parent)
        self.name = "History"
        self._query = None  # type: typing.Optional[sql.Query]

        # advertise that this model filters by URL and title
        self.columns_to_filter = [0, 1]
        self.delete_func = delete_func
        self._empty_prefix = None  # type: typing.Optional[str]

    def _atime_expr(self):
        """If max_items is set, return an expression to limit the query."""
        max_items = config.val.completion.web_history.max_items
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
        raw_pattern = pattern
        if (self._empty_prefix is not None and raw_pattern.startswith(
                self._empty_prefix)):
            log.sql.debug('Skipping query on {} due to '
                          'prefix {} returning nothing.'
                          .format(raw_pattern, self._empty_prefix))
            return
        self._empty_prefix = None

        # escape to treat a user input % or _ as a literal, not a wildcard
        pattern = pattern.replace('%', '\\%')
        pattern = pattern.replace('_', '\\_')
        words = ['%{}%'.format(w) for w in pattern.split(' ')]

        # build a where clause to match all of the words in any order
        # given the search term "a b", the WHERE clause would be:
        # (url LIKE '%a%' OR title LIKE '%a%') AND
        # (url LIKE '%b%' OR title LIKE '%b%')
        where_clause = ' AND '.join(
            "(url LIKE :{val} escape '\\' OR title LIKE :{val} escape '\\')"
            .format(val=i) for i in range(len(words)))

        # replace ' in timestamp-format to avoid breaking the query
        timestamp_format = config.val.completion.timestamp_format or ''
        timefmt = ("strftime('{}', last_atime, 'unixepoch', 'localtime')"
                   .format(timestamp_format.replace("'", "`")))

        try:
            if (not self._query or
                    len(words) != len(self._query.bound_values())):
                # if the number of words changed, we need to generate a new
                # query otherwise, we can reuse the prepared query for
                # performance
                self._query = sql.Query(' '.join([
                    "SELECT url, title, {}".format(timefmt),
                    "FROM CompletionHistory",
                    # the incoming pattern will have literal % and _ escaped we
                    # need to tell SQL to treat '\' as an escape character
                    'WHERE ({})'.format(where_clause),
                    self._atime_expr(),
                    "ORDER BY last_atime DESC",
                ]), forward_only=False)

            with debug.log_time('sql', 'Running completion query'):
                self._query.run(**{
                    str(i): w for i, w in enumerate(words)})
        except sql.KnownError as e:
            # Sometimes, the query we built up was invalid, for example,
            # due to a large amount of words.
            # Also catches failures in the DB we can't solve.
            message.error("Error with SQL query: {}".format(e.text()))
            return
        self.setQuery(self._query.query)
        if not self.rowCount() and not self.canFetchMore():
            self._empty_prefix = raw_pattern

    def removeRows(self, row, _count, _parent=None):
        """Override QAbstractItemModel::removeRows to re-run SQL query."""
        # re-run query to reload updated table
        assert self._query is not None
        with debug.log_time('sql', 'Re-running completion query post-delete'):
            self._query.run()
        self.setQuery(self._query.query)
        while self.rowCount() < row:
            self.fetchMore()
        return True
