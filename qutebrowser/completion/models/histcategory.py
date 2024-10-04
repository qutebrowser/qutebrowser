# SPDX-FileCopyrightText: Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""A completion category that queries the SQL history store."""

from typing import Optional

from qutebrowser.qt.sql import QSqlQueryModel
from qutebrowser.qt.widgets import QWidget

from qutebrowser.misc import sql
from qutebrowser.utils import debug, message, log, utils
from qutebrowser.config import config
from qutebrowser.completion.models import util, BaseCategory


class HistoryCategory(QSqlQueryModel, BaseCategory):

    """A completion category that queries the SQL history store."""

    def __init__(self, *, database: sql.Database,
                 delete_func: util.DeleteFuncType = None,
                 parent: QWidget = None) -> None:
        """Create a new History completion category."""
        super().__init__(parent=parent)
        self._database = database
        self.name = "History"
        self._query: Optional[sql.Query] = None

        # advertise that this model filters by URL and title
        self.columns_to_filter = [0, 1]
        self.delete_func = delete_func
        self._empty_prefix: Optional[str] = None

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

        try:
            if (not self._query or len(words) != len(self._query.bound_values())):
                # if the number of words changed, we need to generate a new
                # query, otherwise we can reuse the prepared query for performance
                max_items = config.val.completion.web_history.max_items
                # HistoryCategory should not be added to the completion in that case.
                assert max_items != 0

                sort_criterion = config.val.completion.web_history.sort_criterion
                if sort_criterion == 'recency':
                    sort_column = 'last_atime DESC'
                elif sort_criterion == 'frequency':
                    sort_column = 'visits DESC, last_atime DESC'
                elif sort_criterion == 'frecency':
                    sort_column = 'frecency DESC'
                else:
                    raise utils.Unreachable(sort_criterion)

                # build a where clause to match all of the words in any order
                # given the search term "a b", the WHERE clause would be:
                # (url LIKE '%a%' OR title LIKE '%a%') AND
                # (url LIKE '%b%' OR title LIKE '%b%')
                where_clause = ' AND '.join(
                    f"(url LIKE :{i} escape '\\' OR title LIKE :{i} escape '\\')"
                    for i in range(len(words))
                )

                # replace ' in timestamp-format to avoid breaking the query
                timestamp_format = (
                    (config.val.completion.timestamp_format or '').replace("'", "`")
                )
                timefmt = (f"strftime('{timestamp_format}', last_atime, 'unixepoch', "
                           "'localtime')")

                self._query = self._database.query(
                    f"SELECT url, title, {timefmt} "
                    "FROM CompletionHistory "
                    # FIXME: does this comment belong here?
                    # the incoming pattern will have literal % and _ escaped we
                    # need to tell SQL to treat '\' as an escape character
                    f"WHERE ({where_clause}) "
                    f"ORDER BY {sort_column} "
                    f"LIMIT {max_items}",
                    forward_only=False
                )

            with debug.log_time('sql', 'Running completion query'):
                self._query.run(**{str(i): w for i, w in enumerate(words)})
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
