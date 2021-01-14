# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import json

import pytest_bdd as bdd
bdd.scenarios('fileselect.feature')


@bdd.when(bdd.parsers.parse('I set up a fake single file fileselector '
                            'selecting "{choosefile}"'))
def set_up_single_fileselector(quteproc, server, tmpdir, choosefile):
    """Set up fileselect.single_file.command to select the file."""
    fileselect_cmd = json.dumps(['echo', choosefile, '>', '{}'])
    quteproc.set_setting('fileselect.handler', 'external')
    quteproc.set_setting('fileselect.single_file.command', fileselect_cmd)


@bdd.when(bdd.parsers.parse('I set up a fake multiple files fileselector '
                            'selecting "{choosefiles}"'))
def set_up_multiple_fileselector(quteproc, server, tmpdir, choosefiles):
    """Set up fileselect.multiple_file.command to select the files."""
    fileselect_cmd = json.dumps([
        'echo', choosefiles, '|',
        'tr', '" "', '"\n"',
        '>', '{}',
    ])
    quteproc.set_setting('fileselect.handler', 'external')
    quteproc.set_setting('fileselect.multiple_file.command', fileselect_cmd)
