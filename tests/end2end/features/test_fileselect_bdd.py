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
def set_up_single_fileselector(quteproc, py_proc, choosefile):
    """Set up fileselect.single_file.command to select the file."""
    set_up_fileselector(
        quteproc=quteproc,
        py_proc=py_proc,
        choosefiles=[choosefile],
        setting_cmd='fileselect.single_file.command'
    )


@bdd.when(bdd.parsers.parse('I set up a fake multiple files fileselector '
                            'selecting "{choosefiles}"'))
def set_up_multiple_fileselector(quteproc, py_proc, choosefiles):
    """Set up fileselect.multiple_file.command to select the files."""
    set_up_fileselector(
        quteproc=quteproc,
        py_proc=py_proc,
        choosefiles=choosefiles.split(' '),
        setting_cmd='fileselect.multiple_files.command'
    )


def set_up_fileselector(quteproc, py_proc, choosefiles, setting_cmd):
    """Set up fileselect.xxx.command to select the file(s)."""
    cmd, args = py_proc(r"""
        import os
        import sys
        tmp_file = sys.argv[1]
        with open(tmp_file, 'w') as f:
            for choosenfile in sys.argv[2:]:
                f.write(os.path.abspath(choosenfile) + "\n")
    """)
    fileselect_cmd = json.dumps([cmd, *args, '{}', *choosefiles])
    quteproc.set_setting('fileselect.handler', 'external')
    quteproc.set_setting(setting_cmd, fileselect_cmd)
