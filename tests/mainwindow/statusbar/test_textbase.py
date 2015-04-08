# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


"""Test TextBase widget."""
from PyQt5.QtCore import Qt
import pytest

from qutebrowser.mainwindow.statusbar.textbase import TextBase


@pytest.mark.parametrize('elidemode, check', [
    (Qt.ElideRight, lambda s: s.endswith('…')),
    (Qt.ElideLeft, lambda s: s.startswith('…')),
    (Qt.ElideMiddle, lambda s: '…' in s),
    (Qt.ElideNone, lambda s: '…' not in s),
])
def test_elided_text(qtbot, elidemode, check):
    """Ensure that a widget too small to hold the entire label text will elide.

    It is difficult to check what is actually being drawn in a portable way, so
    at least we ensure our customized methods are being called and the elided
    string contains the horizontal ellipsis character.

    Args:
        qtbot: pytestqt.plugin.QtBot fixture
        elidemode: parametrized elide mode
        check: function that receives the elided text and must return True
        if the elipsis is placed correctly according to elidemode.
    """
    label = TextBase(elidemode=elidemode)
    qtbot.add_widget(label)
    long_string = 'Hello world! ' * 20
    label.setText(long_string)
    label.resize(100, 50)
    label.show()
    assert check(label._elided_text)  # pylint: disable=protected-access
