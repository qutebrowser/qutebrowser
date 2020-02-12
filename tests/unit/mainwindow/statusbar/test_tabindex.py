# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


"""Test TabIndex widget."""

import pytest

from qutebrowser.mainwindow.statusbar.tabindex import TabIndex


@pytest.fixture
def tabindex(qtbot):
    widget = TabIndex()
    qtbot.add_widget(widget)
    return widget


def test_tab_change(tabindex):
    """Make sure the tab index gets set correctly when switching tabs."""
    tabindex.on_tab_index_changed(0, 2)
    assert tabindex.text() == '[1/2]'
