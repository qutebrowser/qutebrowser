# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import pytest

from PyQt5.QtGui import QClipboard

import pytest_bdd as bdd


bdd.scenarios('yankpaste.feature')


def _get_mode(qapp, what):
    """Get the QClipboard::Mode to use based on a string."""
    if what == 'clipboard':
        return QClipboard.Clipboard
    elif what == 'primary selection':
        assert qapp.clipboard().supportsSelection()
        return QClipboard.Selection
    else:
        raise AssertionError


@bdd.when("selection is supported")
def selection_supported(qapp):
    if not qapp.clipboard().supportsSelection():
        pytest.skip("OS doesn't support primary selection!")

@bdd.when(bdd.parsers.re(r'I put "(?P<content>.*)" into the '
                         r'(?P<what>primary selection|clipboard)'))
def fill_clipboard(qapp, httpbin, what, content):
    mode = _get_mode(qapp, what)
    content = content.replace('(port)', str(httpbin.port))
    qapp.clipboard().setText(content, mode)


@bdd.then(bdd.parsers.re(r'the (?P<what>primary selection|clipboard) should '
                         r'contain "(?P<content>.*)"'))
def clipboard_contains(qapp, httpbin, what, content):
    mode = _get_mode(qapp, what)
    expected = content.replace('(port)', str(httpbin.port))

    data = qapp.clipboard().text(mode=mode)
    assert data == expected
