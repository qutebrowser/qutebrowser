# Copyright 2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for qutebrowser.misc.overlap."""

import pytest

from PyQt5.QtWidgets import QWidget

from qutebrowser.misc import overlap


def test_overlap1(qtbot):
    """Overlap should be found between two widgets."""
    parent = QWidget()
    parent.resize(100, 100)
    qtbot.add_widget(parent)

    widget1 = QWidget(parent=parent)
    widget1.resize(20, 10)
    widget1.move(0, 0)
    widget2 = QWidget(parent=parent)
    widget2.resize(20, 10)
    widget2.move(10, 0)

    overlap_lookup = overlap.OverlapLookup([widget1, widget2])
    assert len(overlap_lookup.overlappings(widget1)) == 1


@pytest.fixture()
def three_widgets(qtbot):
    parent = QWidget()
    parent.resize(100, 100)
    qtbot.add_widget(parent)
    parent.show()

    widget1 = QWidget(parent=parent)
    widget1.resize(20, 10)
    widget1.move(0, 0)
    widget1.show()
    widget2 = QWidget(parent=parent)
    widget2.resize(20, 10)
    widget2.move(10, 0)
    widget2.show()
    widget3 = QWidget(parent=parent)
    widget3.resize(20, 10)
    widget3.move(25, 5)
    widget3.show()

    # have to return parent or objects will be deleted
    return parent


def test_overlap2(three_widgets):
    """Overlaps should be found among three widgets."""
    widget1, widget2, widget3 = three_widgets.children()

    overlap_lookup = overlap.OverlapLookup([widget1, widget2, widget3])
    assert len(overlap_lookup.overlappings(widget1)) == 1
    assert len(overlap_lookup.overlappings(widget2)) == 2
    assert len(overlap_lookup.overlappings(widget3)) == 1


def test_cycling(three_widgets):
    """Cycling widgets should bring widgets at the bottom to the top."""
    widget1, widget2, widget3 = three_widgets.children()
    overlap.cycle([widget1, widget2, widget3])
    post_widgets = three_widgets.children()

    assert post_widgets.index(widget1) > post_widgets.index(widget2)


def test_cycling_rev(three_widgets):
    """Reverse cycling widgets should bring widgets at the top to the bottom."""
    widget1, widget2, widget3 = three_widgets.children()
    overlap.cycle([widget1, widget2, widget3], reverse=True)
    post_widgets = three_widgets.children()

    assert post_widgets.index(widget2) > post_widgets.index(widget3)
