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
import logging

import pytest_bdd as bdd
bdd.scenarios('greasemonkey.feature')

test_gm_script="""
// ==UserScript==
// @name Qutebrowser test userscript
// @namespace invalid.org
// @include http://localhost:*/data/title.html
// @exclude ???
// @run-at document-start
// ==/UserScript==
console.log("Script is running.");
"""

@bdd.when(bdd.parsers.parse('I have a greasemonkey file saved'))
def create_greasemonkey_file(quteproc):
    script_path = os.path.join(quteproc.basedir, 'data', 'greasemonkey')
    os.mkdir(script_path)
    file_path = os.path.join(script_path, 'test.user.js')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(test_gm_script)

