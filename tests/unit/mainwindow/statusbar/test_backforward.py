# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test Backforward widget."""

import pytest

from qutebrowser.mainwindow.statusbar import backforward


@pytest.fixture
def backforward_widget(qtbot):
    widget = backforward.Backforward()
    qtbot.add_widget(widget)
    return widget


@pytest.fixture
def tabs(tabbed_browser_stubs):
    tabbed_browser = tabbed_browser_stubs[0]
    tabbed_browser.widget.current_index = 1
    return tabbed_browser


@pytest.mark.parametrize('can_go_back, can_go_forward, expected_text', [
    (False, False, ''),
    (True, False, '[<]'),
    (False, True, '[>]'),
    (True, True, '[<>]'),
])
def test_widget_state(backforward_widget, tabs,
                      fake_web_tab, can_go_back, can_go_forward,
                      expected_text):
    """Ensure the Backforward widget shows the correct text."""
    tab = fake_web_tab(can_go_back=can_go_back, can_go_forward=can_go_forward)
    tabs.widget.tabs = [tab]
    backforward_widget.enabled = True
    backforward_widget.on_tab_cur_url_changed(tabs)
    assert backforward_widget.text() == expected_text
    assert backforward_widget.isVisible() == bool(expected_text)


def test_state_changes_on_tab_change(backforward_widget, tabs, fake_web_tab):
    """Test we go invisible when switching to a tab without history."""
    tab_with_history = fake_web_tab(can_go_back=True, can_go_forward=True)
    tab_without_history = fake_web_tab(can_go_back=False, can_go_forward=False)
    tabs.widget.tabs = [tab_with_history]
    backforward_widget.enabled = True

    backforward_widget.on_tab_cur_url_changed(tabs)
    assert backforward_widget.isVisible()

    tabs.widget.tabs = [tab_without_history]
    backforward_widget.on_tab_cur_url_changed(tabs)
    assert backforward_widget.text() == ''
    assert not backforward_widget.isVisible()


def test_none_tab(backforward_widget, tabs, fake_web_tab):
    """Make sure nothing crashes when passing None as tab."""
    tab = fake_web_tab(can_go_back=True, can_go_forward=True)
    tabs.widget.tabs = [tab]
    backforward_widget.enabled = True
    backforward_widget.on_tab_cur_url_changed(tabs)

    assert backforward_widget.text() == '[<>]'
    assert backforward_widget.isVisible()

    tabs.widget.current_index = -1
    backforward_widget.on_tab_cur_url_changed(tabs)

    assert backforward_widget.text() == ''
    assert not backforward_widget.isVisible()


def test_not_shown_when_disabled(backforward_widget, tabs, fake_web_tab):
    """The widget shouldn't get shown on an event when it's disabled."""
    tab = fake_web_tab(can_go_back=True, can_go_forward=True)
    tabs.widget.tabs = [tab]

    backforward_widget.enabled = False
    backforward_widget.on_tab_cur_url_changed(tabs)
    assert not backforward_widget.isVisible()

    backforward_widget.on_tab_changed(tab)
    assert not backforward_widget.isVisible()
