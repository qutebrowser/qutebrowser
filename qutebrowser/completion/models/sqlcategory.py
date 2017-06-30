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

"""A completion model backed by SQL tables."""

import re

from PyQt5.QtSql import QSqlQueryModel

from qutebrowser.misc import sql
from qutebrowser.utils import debug
from qutebrowser.commands import cmdexc


class SqlCategory(QSqlQueryModel):

    """Wraps a SqlQuery for use as a completion category."""

    def __init__(self, name, *, title=None, filter_fields, sort_by=None,
                 sort_order=None, select='*', where=None, group_by=None,
                 delete_func=None, parent=None):
        """Create a new completion category backed by a sql table.

        Args:
            name: Name of the table in the database.
            title: Title of category, defaults to table name.
            filter_fields: Names of fields to apply filter pattern to.
            select: A custom result column expression for the select statement.
            where: An optional clause to filter out some rows.
            sort_by: The name of the field to sort by, or None for no sorting.
            sort_order: Either 'asc' or 'desc', if sort_by is non-None
            delete_func: Callback to delete a selected item.
        """
        super().__init__(parent=parent)
        self.name = title or name

        querystr = 'select {} from {} where ('.format(select, name)
        # the incoming pattern will have literal % and _ escaped with '\'
        # we need to tell sql to treat '\' as an escape character
        querystr += ' or '.join("{} like :pattern escape '\\'".format(f)
                                for f in filter_fields)
        querystr += ')'

        if where:
            querystr += ' and ' + where
        if group_by:
            querystr += ' group by {}'.format(group_by)
        if sort_by:
            assert sort_order in ['asc', 'desc'], sort_order
            querystr += ' order by {} {}'.format(sort_by, sort_order)

        self._query = sql.Query(querystr, forward_only=False)

        # map filter_fields to indices
        col_query = sql.Query('SELECT * FROM {} LIMIT 1'.format(name))
        rec = col_query.run().record()
        self.columns_to_filter = [rec.indexOf(n) for n in filter_fields]
        self.delete_func = delete_func

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
            self._query.run(pattern=pattern)
        self.setQuery(self._query)

    def delete_cur_item(self, index):
        """Delete the row at the given index."""
        if not self.delete_func:
            raise cmdexc.CommandError("Cannot delete this item.")
        data = [self.data(index.sibling(index.row(), i))
                for i in range(self.columnCount())]
        self.delete_func(data)
        # re-run query to reload updated table
        with debug.log_time('sql', 'Re-running completion query post-delete'):
            self._query.run()
        self.setQuery(self._query)
