import logging

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.utils import objreg, usertypes
from qutebrowser.browser import commands


not_finished_statuses = [
    usertypes.LoadStatus.none,
    usertypes.LoadStatus.loading,
]


@pytest.fixture()
def browser(caplog, qtbot, real_tabbed_browser):
    real_tabbed_browser.container.expose()

    command_dispatcher = commands.CommandDispatcher(
        real_tabbed_browser._win_id, real_tabbed_browser)

    with caplog.at_level(logging.WARNING):
        # For some reason, TabBarStyle fails to get the tab layout for those
        # tabs, so it fails to render properly and logs a warning.

        command_dispatcher.openurl(
            url=QUrl("about:blank"),
        )
        command_dispatcher.openurl(
            url=QUrl("about:blank"),
            bg=True,
        )
        command_dispatcher.openurl(
            url=QUrl("about:blank"),
            bg=True,
        )

    signals = [
        tab.load_finished
        for tab in real_tabbed_browser.widgets()
        if tab.load_status() in not_finished_statuses
    ]
    with qtbot.waitSignals(signals):
        pass

    return real_tabbed_browser


def test_background_tabs_webcontent_hidden(qtbot, browser):
    visibility_states = {}
    for idx, tab in enumerate(browser.widgets()):
        with qtbot.waitCallback() as callback:
            tab.run_js_async(
                "document.hidden",
                callback,
            )
        visibility_states[idx] = callback.args[0]

    assert visibility_states == {
        0: False,
        1: True,
        2: True,
    }


@pytest.mark.xfail(True, reason='Would need real session manager')
def test_session_load_backround_tabs_webcontent_hidden(qtbot, browser):
    session_manager = objreg.get("session-manager")
    session_manager.save("three-blank-tabs")
    session_manager.load("three-blank-tabs")
    new_browser = objreg.get("tabbed-browser", scope="window", window=1)
    signals = [
        tab.load_finished
        for tab in new_browser.widgets()
        if tab.load_status() in not_finished_statuses
    ]
    with qtbot.waitSignals(signals):
        pass

    visibility_states = {}
    for idx, tab in enumerate(new_browser.widgets()):
        with qtbot.waitCallback() as callback:
            tab.run_js_async(
                "document.hidden",
                callback,
            )
        visibility_states[idx] = callback.args[0]

    assert visibility_states == {
        0: False,
        1: True,
        2: True,
    }
