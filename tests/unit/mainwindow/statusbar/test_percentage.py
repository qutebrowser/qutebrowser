# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


"""Test Percentage widget."""

import pytest

from qutebrowser.mainwindow.statusbar.percentage import Percentage


@pytest.fixture
def percentage(qtbot):
    """Fixture providing a Percentage widget."""
    widget = Percentage()
    qtbot.add_widget(widget)
    return widget


@pytest.mark.parametrize('y, expected', [
    (0, '[top]'),
    (100, '[bot]'),
    (75, '[75%]'),
    (25, '[25%]'),
    (5, '[ 5%]'),
    (None, '[???]'),
])
def test_percentage_text(percentage, y, expected):
    """Test text displayed by the widget based on the y position of a page.

    Args:
        y: y position of the page as an int in the range [0, 100].
           parametrized.
        expected: expected text given y position. parametrized.
    """
    percentage.set_perc(x=None, y=y)
    assert percentage.text() == expected


def test_tab_change(percentage, fake_web_tab):
    """Make sure the percentage gets changed correctly when switching tabs."""
    percentage.set_perc(x=None, y=10)
    tab = fake_web_tab(scroll_pos_perc=(0, 20))
    percentage.on_tab_changed(tab)
    assert percentage.text() == '[20%]'
