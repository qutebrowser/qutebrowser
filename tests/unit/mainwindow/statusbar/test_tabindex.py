# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test TabIndex widget."""

import pytest

from qutebrowser.mainwindow.statusbar.tabindex import TabIndex, TabIndexWidget


@pytest.fixture
def tabindex(qtbot):
    widget = TabIndex(widget=TabIndexWidget())
    qtbot.add_widget(widget.widget)
    return widget


def test_tab_change(tabindex):
    """Make sure the tab index gets set correctly when switching tabs."""
    tabindex.on_tab_index_changed(0, 2)
    assert tabindex.widget.text() == '[1/2]'
