# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import sys
import os.path
import subprocess

import pytest
import pytest_bdd as bdd

import qutebrowser
from qutebrowser.utils import docutils

bdd.scenarios('qutescheme.feature')


@bdd.when("the documentation is up to date")
def update_documentation():
    """Update the docs before testing :help."""
    base_path = os.path.dirname(os.path.abspath(qutebrowser.__file__))
    doc_path = os.path.join(base_path, 'html', 'doc')
    script_path = os.path.join(base_path, '..', 'scripts')

    try:
        os.mkdir(doc_path)
    except FileExistsError:
        pass

    files = os.listdir(doc_path)
    if files and all(docutils.docs_up_to_date(p) for p in files):
        return

    try:
        subprocess.run(['asciidoc'], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except OSError:
        pytest.skip("Docs outdated and asciidoc unavailable!")

    update_script = os.path.join(script_path, 'asciidoc2html.py')
    subprocess.run([sys.executable, update_script])
