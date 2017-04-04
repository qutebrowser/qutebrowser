# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import os.path

import pytest_bdd as bdd

from PyQt5.QtSql import QSqlDatabase, QSqlQuery

bdd.scenarios('history.feature')


@bdd.then(bdd.parsers.parse("the history file should contain:\n{expected}"))
def check_history(quteproc, httpbin, expected):
    path = os.path.join(quteproc.basedir, 'data', 'history.sqlite')
    db = QSqlDatabase.addDatabase('QSQLITE')
    db.setDatabaseName(path)
    assert db.open(), 'Failed to open history database'
    query = db.exec_('select * from History')
    actual = []
    while query.next():
        rec = query.record()
        url = rec.value(0)
        title = rec.value(1)
        redirect = rec.value(3)
        actual.append('{} {} {}'.format('r' * redirect, url, title).strip())
    db = None
    QSqlDatabase.removeDatabase(QSqlDatabase.database().connectionName())
    assert actual == expected.replace('(port)', str(httpbin.port)).splitlines()


@bdd.then("the history file should be empty")
def check_history_empty(quteproc, httpbin):
    check_history(quteproc, httpbin, '')
