# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2021 Ryan Roden-Corrent (rcorre) <ryan@rcorre.net>
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

"""Test the keyhint widget."""

import pytest
from PyQt5.QtCore import QPoint

from qutebrowser.utils import usertypes
from qutebrowser.misc.scrollhintwidget import ScrollHintView


def expected_text(*args):
    """Helper to format text we expect the KeyHintView to generate.

    Args:
        args: One tuple for each row in the expected output.
              Tuples are of the form: (prefix, color, suffix, command).
    """
    text = '<table>'
    for group in args:
        text += ("<tr>"
                 "<td>{}</td>"
                 "<td style='padding-left: 2ex'>({}%, {}%)</td>"
                 "</tr>").format(*group)

    return text + '</table>'


@pytest.fixture
def scrollhint(qtbot, config_stub, tabbed_browser_stubs):
    """Fixture to initialize a KeyHintView."""
    config_stub.val.colors.keyhint.suffix.fg = 'yellow'
    view = ScrollHintView(0, tabbed_browser_stubs[0], None)
    qtbot.add_widget(view)
    assert view.text() == ''
    return view


def test_show_and_hide(qtbot, scrollhint, tabbed_browser_stubs):
    tabbed_browser_stubs[0].list_local_marks_perc = lambda: {}
    assert not scrollhint.isVisible()

    # should ignore these
    scrollhint.on_mode_entered(usertypes.KeyMode.normal)
    assert not scrollhint.isVisible()
    scrollhint.on_mode_left(usertypes.KeyMode.normal)
    assert not scrollhint.isVisible()

    with qtbot.waitSignal(scrollhint.update_geometry):
        with qtbot.waitExposed(scrollhint):
            scrollhint.on_mode_entered(usertypes.KeyMode.jump_mark)

    assert scrollhint.isVisible()
    assert scrollhint.text() == "<table></table>"

    scrollhint.on_mode_left(usertypes.KeyMode.jump_mark)
    assert not scrollhint.isVisible()


def test_text(qtbot, scrollhint, tabbed_browser_stubs):
    tabbed_browser_stubs[0].list_local_marks_perc = lambda: {
        "a": QPoint(0, 50),
        "b": QPoint(0, 10),
        "c": QPoint(25, 0),
        "d": QPoint(25, 25),
        "e": QPoint(100, 100),
    }

    with qtbot.waitSignal(scrollhint.update_geometry):
        with qtbot.waitExposed(scrollhint):
            scrollhint.on_mode_entered(usertypes.KeyMode.jump_mark)

    # should be sorted by the last value (y coordinate)
    assert scrollhint.text() == expected_text(
        ("c", 25, 0),
        ("b", 0, 10),
        ("d", 25, 25),
        ("a", 0, 50),
        ("e", 100, 100),
    )
