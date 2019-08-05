import pytest

from PyQt5.QtCore import QUrl

from qutebrowser import app, qutebrowser
from qutebrowser.utils import objreg, usertypes


@pytest.fixture(scope="module")
def qute():
    arg_parser = qutebrowser.get_argparser()
    args = arg_parser.parse_args(["-T"])
    app.run(args, no_mainloop=True)
    return app.q_app


not_finished_statuses = [
    usertypes.LoadStatus.none,
    usertypes.LoadStatus.loading,
]


@pytest.fixture()
def browser(qtbot):
    tabbed_browser = objreg.get("tabbed-browser", scope="window", window=0)
    command_dispatcher = objreg.get("command-dispatcher", scope="window", window=0)
    command_dispatcher.tab_only()
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
        for tab in tabbed_browser.widgets()
        if tab.load_status() in not_finished_statuses
    ]
    with qtbot.waitSignals(signals):
        pass
    return tabbed_browser


def test_backround_tabs_webcontent_hidden(qute, qtbot, browser):
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

def test_session_load_backround_tabs_webcontent_hidden(qute, qtbot, browser):
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
