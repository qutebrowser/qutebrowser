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

"""Tests for browser.webpage."""

import textwrap

from qutebrowser.browser import webpage


def test_generate_pdfjs_script():
    data = b'\x00foobar\xFF'
    expected = textwrap.dedent("""
        var data = new Uint8Array([
        0,102,111,111,98,97,114,255,]);
        PDFJS.getDocument(data).then(function(pdf) {
            PDFView.load(pdf);
        });
    """)
    actual = webpage._generate_pdfjs_script(data)
    assert actual.strip() == expected.strip()
