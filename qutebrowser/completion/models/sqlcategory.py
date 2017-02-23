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


class SqlCategory(QSqlQueryModel):
    """Wraps a SqlQuery for use as a completion category."""

    def __init__(self, name, *, sort_by, sort_order, select, where,
                 columns_to_filter, parent=None):
        super().__init__(parent=parent)
        self.name = name

        query = sql.run_query('select * from {} limit 1'.format(name))
        self._fields = [query.record().fieldName(i) for i in columns_to_filter]

        querystr = 'select {} from {} where ('.format(select, name)
        # the incoming pattern will have literal % and _ escaped with '\'
        # we need to tell sql to treat '\' as an escape character
        querystr += ' or '.join("{} like ? escape '\\'".format(f)
                                for f in self._fields)
        querystr += ')'
        if where:
            querystr += ' and ' + where

        if sort_by:
            assert sort_order == 'asc' or sort_order == 'desc'
            querystr += ' order by {} {}'.format(sort_by, sort_order)

        self._querystr = querystr
        self.set_pattern('')

    def set_pattern(self, pattern):
        # escape to treat a user input % or _ as a literal, not a wildcard
        pattern = pattern.replace('%', '\\%')
        pattern = pattern.replace('_', '\\_')
        # treat spaces as wildcards to match any of the typed words
        pattern = re.sub(r' +', '%', pattern)
        pattern = '%{}%'.format(pattern)
        query = sql.run_query(self._querystr, [pattern for _ in self._fields])
        self.setQuery(query)
