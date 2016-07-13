# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import json
import os.path
import subprocess

import pytest
import pytest_bdd as bdd

import qutebrowser
from qutebrowser.utils import docutils
from qutebrowser.browser import pdfjs

bdd.scenarios('misc.feature')


@bdd.when("the documentation is up to date")
def update_documentation():
    """Update the docs before testing :help."""
    base_path = os.path.dirname(os.path.abspath(qutebrowser.__file__))
    doc_path = os.path.join(base_path, 'html', 'doc')
    script_path = os.path.join(base_path, '..', 'scripts')

    if not os.path.exists(doc_path):
        # On CI, we can test this without actually building the docs
        return

    if all(docutils.docs_up_to_date(p) for p in os.listdir(doc_path)):
        return

    try:
        subprocess.call(['asciidoc'], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
    except OSError:
        pytest.skip("Docs outdated and asciidoc unavailable!")

    update_script = os.path.join(script_path, 'asciidoc2html.py')
    subprocess.call([sys.executable, update_script])


@bdd.given('pdfjs is available')
def pdfjs_available():
    if not pdfjs.is_available():
        pytest.skip("No pdfjs installation found.")


@bdd.then(bdd.parsers.parse('the cookie {name} should be set to {value}'))
def check_cookie(quteproc, name, value):
    """Check if a given cookie is set correctly.

    This assumes we're on the httpbin cookies page.
    """
    content = quteproc.get_content()
    data = json.loads(content)
    print(data)
    assert data['cookies'][name] == value


@bdd.then(bdd.parsers.parse('the PDF {filename} should exist in the tmpdir'))
def pdf_exists(quteproc, tmpdir, filename):
    path = tmpdir / filename
    data = path.read_binary()
    assert data.startswith(b'%PDF')
