# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
bdd.scenarios('history.feature')


@bdd.then(bdd.parsers.parse("the history file should contain:\n{expected}"))
def check_history(quteproc, httpbin, expected):
    history_file = os.path.join(quteproc.basedir, 'data', 'history')
    quteproc.send_cmd(':save history')
    quteproc.wait_for(message=':save saved history')

    expected = expected.replace('(port)', str(httpbin.port)).splitlines()

    with open(history_file, 'r', encoding='utf-8') as f:
        lines = []
        for line in f:
            if not line.strip():
                continue
            print('history line: ' + line)
            atime, line = line.split(' ', maxsplit=1)
            line = line.rstrip()
            if '-' in atime:
                flags = atime.split('-')[1]
                line = '{} {}'.format(flags, line)
            lines.append(line)

    assert lines == expected


@bdd.then("the history file should be empty")
def check_history_empty(quteproc, httpbin):
    check_history(quteproc, httpbin, '')
