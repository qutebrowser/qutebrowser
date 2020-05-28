# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Test Backforward widget."""

import pytest

from qutebrowser.mainwindow.statusbar import backforward


@pytest.fixture
def backforward_widget(qtbot):
    widget = backforward.Backforward()
    qtbot.add_widget(widget)
    return widget


@pytest.mark.parametrize('can_go_back, can_go_forward, expected_text', [
    (False, False, ''),
    (True, False, '[<]'),
    (False, True, '[>]'),
    (True, True, '[<>]'),
])
def test_backforward_widget(backforward_widget, tabbed_browser_stubs,
                            fake_web_tab, can_go_back, can_go_forward,
                            expected_text):
    """Ensure the Backforward widget shows the correct text."""
    tab = fake_web_tab(can_go_back=can_go_back, can_go_forward=can_go_forward)
    tabbed_browser = tabbed_browser_stubs[0]
    tabbed_browser.widget.current_index = 1
    tabbed_browser.widget.tabs = [tab]
    backforward_widget.enabled = True
    backforward_widget.on_tab_cur_url_changed(tabbed_browser)
    assert backforward_widget.text() == expected_text
    assert backforward_widget.isVisible() == bool(expected_text)

    # Check that the widget stays hidden if not in the statusbar
    backforward_widget.enabled = False
    backforward_widget.hide()
    backforward_widget.on_tab_cur_url_changed(tabbed_browser)
    assert backforward_widget.isHidden()

    # Check that the widget gets reset if empty.
    if can_go_back and can_go_forward:
        tab = fake_web_tab(can_go_back=False, can_go_forward=False)
        tabbed_browser.widget.tabs = [tab]
        backforward_widget.enabled = True
        backforward_widget.on_tab_cur_url_changed(tabbed_browser)
        assert backforward_widget.text() == ''
        assert not backforward_widget.isVisible()


def test_none_tab(backforward_widget, tabbed_browser_stubs, fake_web_tab):
    """Make sure nothing crashes when passing None as tab."""
    tab = fake_web_tab(can_go_back=True, can_go_forward=True)
    tabbed_browser = tabbed_browser_stubs[0]
    tabbed_browser.widget.current_index = 1
    tabbed_browser.widget.tabs = [tab]
    backforward_widget.enabled = True
    backforward_widget.on_tab_cur_url_changed(tabbed_browser)

    assert backforward_widget.text() == '[<>]'
    assert backforward_widget.isVisible()

    tabbed_browser.widget.current_index = -1
    backforward_widget.on_tab_cur_url_changed(tabbed_browser)

    assert backforward_widget.text() == ''
    assert not backforward_widget.isVisible()
