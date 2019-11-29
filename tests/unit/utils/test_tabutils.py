# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

"""Tests for qutebrowser.utils.tabutils."""

import attr
import pytest
from PyQt5.QtCore import QUrl
from qutebrowser.api import cmdutils
from qutebrowser.utils import objreg, tabutils


@pytest.fixture
def stub_tabs(fake_web_tab, tabbed_browser_stubs):
    tabbed_browser_stubs[0].widget.tabs = [
        fake_web_tab(QUrl('https://github.com'), 'GitHub'),
        fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia'),
        fake_web_tab(QUrl('https://duckduckgo.com'), 'DuckDuckGo'),
    ]

    tab_1_1 = fake_web_tab(QUrl('https://wiki.archlinux.org'), 'ArchWiki')
    tab_1_1.win_id = 1

    tab_1_2 = fake_web_tab(QUrl('https://google.com'), 'Google')
    tab_1_2.win_id = 1

    tabbed_browser_stubs[1].widget.tabs = [tab_1_1, tab_1_2]

    yield


@pytest.fixture
def stub_app():
    win_0 = FakeWindow(0)
    win_1 = FakeWindow(1)
    win_2 = FakeWindow(2)

    app = FakeApp([win_0, win_1, win_2])
    app.set_active_window(win_1)
    objreg.register('app', app)

    yield

    objreg.delete('app')


@pytest.fixture
def stub_app_no_windows():
    app = FakeApp([])
    objreg.register('app', app)

    yield

    objreg.delete('app')


class FakeWindow():
    def __init__(self, win_id):
        self.win_id = win_id
        self._active = False
        self._raised = False

    def activateWindow(self):
        self._active = True

    def raise_(self):
        self._raised = True

    def isactive(self):
        return self._active

    def israised(self):
        return self._raised


class FakeApp():
    def __init__(self, windows):
        self.active_window = None
        self.windows = attr.ib

    def activeWindow(self):
        return self.active_window

    def set_active_window(self, window):
        self.active_window = window


def test_all_tabs(stub_tabs):
    tabs = [(t.win_id, t.url(), t.title()) for t in tabutils.all_tabs()]

    assert tabs == [
        (0, QUrl("https://github.com"), "GitHub"),
        (0, QUrl("https://wikipedia.org"), "Wikipedia"),
        (0, QUrl("https://duckduckgo.com"), "DuckDuckGo"),
        (1, QUrl("https://wiki.archlinux.org"), "ArchWiki"),
        (1, QUrl("https://google.com"), "Google"),
    ]


def test_all_tabs_skip_win_id(stub_tabs):
    tabs = [(t.win_id, t.url(), t.title()) for t in
            tabutils.all_tabs(skip_win_id=0)]

    assert list(tabs) == [
        (1, QUrl("https://wiki.archlinux.org"), "ArchWiki"),
        (1, QUrl("https://google.com"), "Google"),
    ]


def test_all_tabs_shutting_down(stub_tabs, tabbed_browser_stubs):
    tabbed_browser_stubs[0].shutting_down = True

    tabs = [(t.win_id, t.url(), t.title()) for t in tabutils.all_tabs()]

    assert list(tabs) == [
        (1, QUrl("https://wiki.archlinux.org"), "ArchWiki"),
        (1, QUrl("https://google.com"), "Google"),
    ]


def test_all_tabs_by_window(stub_tabs):
    tabs_by_window = {}

    for w, tabs in tabutils.all_tabs_by_window().items():
        tabs = [(t.win_id, t.url(), t.title()) for t in tabs]
        tabs_by_window[w] = tabs

    assert tabs_by_window == {
        0: [
            (0, QUrl("https://github.com"), "GitHub"),
            (0, QUrl("https://wikipedia.org"), "Wikipedia"),
            (0, QUrl("https://duckduckgo.com"), "DuckDuckGo"),
        ],
        1: [
            (1, QUrl("https://wiki.archlinux.org"), "ArchWiki"),
            (1, QUrl('https://google.com'), 'Google'),
        ]
    }


def test_all_tabs_by_window_skip_win_id(stub_tabs):
    tabs_by_window = {}

    for w, tabs in tabutils.all_tabs_by_window(0).items():
        tabs = [(t.win_id, t.url(), t.title()) for t in tabs]
        tabs_by_window[w] = tabs

    assert tabs_by_window == {
        1: [
            (1, QUrl("https://wiki.archlinux.org"), "ArchWiki"),
            (1, QUrl('https://google.com'), 'Google'),
        ]
    }


def test_delete_tab_index_on_0(stub_tabs):
    tabutils.delete_tab(0)(("1/2", "", ""))

    tabs = ((t.title()) for t in tabutils.all_tabs())
    assert list(tabs) == ["GitHub", "Wikipedia", "DuckDuckGo", "ArchWiki"]


def test_delete_tab_index_on_2(stub_tabs):
    tabutils.delete_tab(2)(("", "", "0/1"))

    tabs = ((t.title()) for t in tabutils.all_tabs())
    assert list(tabs) == ["Wikipedia", "DuckDuckGo", "ArchWiki", "Google"]


def test_tab_for_url_no_match(stub_tabs, config_stub):
    config_stub.val.tabs.switch_to_open_url = True

    url = QUrl("foobar")
    tab = tabutils.tab_for_url(url)

    assert tab is None


def test_tab_for_url(stub_tabs, config_stub):
    config_stub.val.tabs.switch_to_open_url = True

    url = QUrl("https://wiki.archlinux.org")
    tab = tabutils.tab_for_url(url)

    assert tab.url() == url
    assert tab.title() == "ArchWiki"
    assert tab.win_id == 1


def test_resolve_tab_index_win_id_and_index(stub_tabs):
    tab = tabutils.resolve_tab_index("0/1")

    assert tab.url() == QUrl("https://github.com")
    assert tab.title() == "GitHub"
    assert tab.win_id == 0


def test_resolve_tab_index_substring(stub_tabs):
    tab = tabutils.resolve_tab_index("github")

    assert tab.url() == QUrl("https://github.com")
    assert tab.title() == "GitHub"
    assert tab.win_id == 0


def test_resolve_tab_index_substring_no_match(stub_tabs):
    with pytest.raises(cmdutils.CommandError) as excinfo:
        tabutils.resolve_tab_index("foobarbaz")

    assert str(excinfo.value) == "No matching tab for: foobarbaz"


def test_resolve_tab_index_index(stub_app, stub_tabs):
    tab = tabutils.resolve_tab_index("1")

    assert tab.url() == QUrl("https://wiki.archlinux.org")
    assert tab.title() == "ArchWiki"
    assert tab.win_id == 1


def test_resolve_tab_index_invalid_win_id(stub_tabs):
    with pytest.raises(cmdutils.CommandError) as excinfo:
        tabutils.resolve_tab_index("3/1")

    assert str(excinfo.value) == "There's no window with id 3!"


def test_resolve_tab_index_no_active_window(stub_app_no_windows):
    with pytest.raises(cmdutils.CommandError) as excinfo:
        tabutils.resolve_tab_index("1")

    assert str(excinfo.value) == \
        "No window specified and couldn't find active window!"


def test_switch_to_tab(stub_tabs, tabbed_browser_stubs, fake_web_tab):
    widget = tabbed_browser_stubs[0].widget
    win_0 = FakeWindow(0)
    widget.setWindow(win_0)

    win_1 = FakeWindow(1)
    tabbed_browser_stubs[1].widget.setWindow(win_1)

    tab = fake_web_tab(QUrl('https://wikipedia.org'), 'Wikipedia', 2)
    tab.win_id = 0

    tabutils.switch_to_tab(tab)

    assert win_0.isactive()
    assert win_0.israised()
    assert widget.current_widget.url() == widget.tabs[1].url() == tab.url()
    assert widget.current_widget.title() == widget.tabs[1].title() == \
        tab.title()
    assert widget.current_widget.win_id == widget.tabs[1].win_id == tab.win_id

    assert not win_1.isactive()
    assert not win_1.israised()
