# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Daniel Schadt
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

import textwrap

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.browser import pdfjs
from qutebrowser.browser.webkit.network import qutescheme
from qutebrowser.utils import objreg


@pytest.yield_fixture
def js_bridge():
    bridge = qutescheme.JSBridge()
    objreg.register('js-bridge', bridge)
    yield bridge
    objreg.delete('js-bridge')


def test_generate_pdfjs_script(js_bridge):
    test_data = b'foobar'
    script = pdfjs._generate_pdfjs_script(test_data).strip()
    assert len(js_bridge.peek_pdfs()) == 1
    data_ident = js_bridge.peek_pdfs()[0][0]
    expected = textwrap.dedent("""
        PDFJS.verbosity = PDFJS.VERBOSITY_LEVELS.info;
        var _init_params = {
            data: new Uint8Array(window.qute.get_pdf("$init")),
        };
        PDFJS.getDocument(_init_params).then(
            function (doc) { PDFView.load(doc); }
        );
    """).strip().replace('$init', data_ident)
    assert script == expected


def test_fix_urls():
    page = textwrap.dedent("""
        <html>
        <script src="viewer.js"></script>
        <link href="viewer.css">
        <script src="unrelated.js"></script>
        </html>
    """).strip()

    expected = textwrap.dedent("""
        <html>
        <script src="qute://pdfjs/web/viewer.js"></script>
        <link href="qute://pdfjs/web/viewer.css">
        <script src="unrelated.js"></script>
        </html>
    """).strip()

    actual = pdfjs.fix_urls(page)
    assert actual == expected


@pytest.mark.parametrize('path, expected', [
    ('web/viewer.js', 'viewer.js'),
    ('build/locale/foo.bar', 'locale/foo.bar'),
    ('viewer.js', 'viewer.js'),
    ('foo/viewer.css', 'foo/viewer.css'),
])
def test_remove_prefix(path, expected):
    assert pdfjs._remove_prefix(path) == expected
