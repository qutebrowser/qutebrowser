# SPDX-FileCopyrightText: Freya Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.utils.tabutils."""

import pytest
from qutebrowser.qt.core import QUrl
from qutebrowser.utils import tabutils


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


class FakeWindow:

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


def test_all_tabs(stub_tabs):
    tabs = [(t.win_id, t.url(), t.title()) for t in tabutils.all_tabs()]

    assert tabs == [
        (0, QUrl('https://github.com'), 'GitHub'),
        (0, QUrl('https://wikipedia.org'), 'Wikipedia'),
        (0, QUrl('https://duckduckgo.com'), 'DuckDuckGo'),
        (1, QUrl('https://wiki.archlinux.org'), 'ArchWiki'),
        (1, QUrl('https://google.com'), 'Google'),
    ]


def test_all_tabs_skip_win_id(stub_tabs):
    tabs = [(t.win_id, t.url(), t.title()) for t in
            tabutils.all_tabs(skip_win_id=0)]

    assert list(tabs) == [
        (1, QUrl('https://wiki.archlinux.org'), 'ArchWiki'),
        (1, QUrl('https://google.com'), 'Google'),
    ]


def test_all_tabs_shutting_down(stub_tabs, tabbed_browser_stubs):
    tabbed_browser_stubs[0].is_shutting_down = True

    tabs = [(t.win_id, t.url(), t.title()) for t in tabutils.all_tabs()]

    assert list(tabs) == [
        (1, QUrl('https://wiki.archlinux.org'), 'ArchWiki'),
        (1, QUrl('https://google.com'), 'Google'),
    ]


def test_all_tabs_by_window(stub_tabs):
    tabs_by_window = {}

    for w, tabs in tabutils.all_tabs_by_window().items():
        tabs = [(t.win_id, t.url(), t.title()) for t in tabs]
        tabs_by_window[w] = tabs

    assert tabs_by_window == {
        0: [
            (0, QUrl('https://github.com'), 'GitHub'),
            (0, QUrl('https://wikipedia.org'), 'Wikipedia'),
            (0, QUrl('https://duckduckgo.com'), 'DuckDuckGo'),
        ],
        1: [
            (1, QUrl('https://wiki.archlinux.org'), 'ArchWiki'),
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
            (1, QUrl('https://wiki.archlinux.org'), 'ArchWiki'),
            (1, QUrl('https://google.com'), 'Google'),
        ]
    }


def test_all_tabs_by_window_skips_empty_shutting_down(stub_tabs,
                                                      tabbed_browser_stubs):
    tabbed_browser_stubs[0].is_shutting_down = True

    tabs_by_window = tabutils.all_tabs_by_window()

    assert list(tabs_by_window) == [1]


def test_delete_tab_index_on_0(stub_tabs):
    tabutils.delete_tab(0)(('1/2', '', ''))

    tabs = ((t.title()) for t in tabutils.all_tabs())
    assert list(tabs) == ['GitHub', 'Wikipedia', 'DuckDuckGo', 'ArchWiki']


def test_delete_tab_index_on_2(stub_tabs):
    tabutils.delete_tab(2)(('', '', '0/1'))

    tabs = ((t.title()) for t in tabutils.all_tabs())
    assert list(tabs) == ['Wikipedia', 'DuckDuckGo', 'ArchWiki', 'Google']


def test_tab_for_url_no_match(stub_tabs):
    assert tabutils.tab_for_url(QUrl('foobar'), private=False) is None


def test_tab_for_url(stub_tabs):
    tab = tabutils.tab_for_url(QUrl('https://wiki.archlinux.org'),
                               private=False)

    assert tab.url() == QUrl('https://wiki.archlinux.org')
    assert tab.title() == 'ArchWiki'
    assert tab.win_id == 1


def test_tab_for_url_same_privacy(stub_tabs, tabbed_browser_stubs):
    tabbed_browser_stubs[0].widget.tabs[0].is_private = True

    tab = tabutils.tab_for_url(QUrl('https://github.com'), private=True)

    assert tab is not None
    assert tab.title() == 'GitHub'


def test_tab_for_url_skips_other_privacy(stub_tabs, tabbed_browser_stubs):
    tabbed_browser_stubs[0].widget.tabs[0].is_private = True

    assert tabutils.tab_for_url(QUrl('https://github.com'),
                                private=False) is None


def test_tab_for_url_normal_tab_none_privacy(stub_tabs, tabbed_browser_stubs):
    """A normal tab whose is_private is None still matches a normal open.

    Real browser tabs report is_private as None, not False, so a strict `==`
    comparison against the bool False excludes them and a duplicate opens.
    """
    tabbed_browser_stubs[0].widget.tabs[0].is_private = None

    tab = tabutils.tab_for_url(QUrl('https://github.com'), private=False)

    assert tab is not None
    assert tab.title() == 'GitHub'


def test_tab_for_url_private_open_skips_normal_tab(stub_tabs,
                                                   tabbed_browser_stubs):
    """A private open never matches a normal tab, even one with None privacy.

    bool(None) == bool(True) is False, so the privacy boundary still rejects
    the match and a private context cannot land on a normal tab.
    """
    tabbed_browser_stubs[0].widget.tabs[0].is_private = None

    assert tabutils.tab_for_url(QUrl('https://github.com'),
                                private=True) is None


def test_switch_to_open_url_switches(stub_tabs, tabbed_browser_stubs,
                                     config_stub):
    """With the option on and a matching tab, the helper switches to it."""
    config_stub.val.tabs.switch_to_open_url = True
    win_0 = FakeWindow(0)
    tabbed_browser_stubs[0].widget.setWindow(win_0)

    url = QUrl('https://github.com')
    tab = tabutils.switch_to_open_url(url, private=False)

    assert tab is not None
    assert tab.url() == url
    assert win_0.isactive()
    assert tabbed_browser_stubs[0].widget.current_widget.url() == url


def test_switch_to_open_url_disabled(stub_tabs, tabbed_browser_stubs,
                                     config_stub):
    """With the option off, the helper returns None and does not switch."""
    config_stub.val.tabs.switch_to_open_url = False
    win_0 = FakeWindow(0)
    tabbed_browser_stubs[0].widget.setWindow(win_0)

    tab = tabutils.switch_to_open_url(QUrl('https://github.com'),
                                      private=False)

    assert tab is None
    assert not win_0.isactive()


def test_switch_to_open_url_reuse_false(stub_tabs, tabbed_browser_stubs,
                                        config_stub):
    """reuse=False suppresses the switch even with the option on."""
    config_stub.val.tabs.switch_to_open_url = True
    win_0 = FakeWindow(0)
    tabbed_browser_stubs[0].widget.setWindow(win_0)

    tab = tabutils.switch_to_open_url(QUrl('https://github.com'),
                                      private=False, reuse=False)

    assert tab is None
    assert not win_0.isactive()


def test_switch_to_open_url_no_match(stub_tabs, config_stub):
    """With no matching tab, the helper returns None."""
    config_stub.val.tabs.switch_to_open_url = True

    assert tabutils.switch_to_open_url(QUrl('https://no-such-tab.example'),
                                       private=False) is None


def test_switch_to_open_url_private_skips_normal_tab(stub_tabs, config_stub):
    """A private switch never lands on a normal tab (privacy boundary)."""
    config_stub.val.tabs.switch_to_open_url = True

    assert tabutils.switch_to_open_url(QUrl('https://github.com'),
                                       private=True) is None


def test_switch_to_open_url_normal_skips_private_tab(stub_tabs,
                                                     tabbed_browser_stubs,
                                                     config_stub):
    """A normal switch never lands on a private tab (privacy boundary)."""
    config_stub.val.tabs.switch_to_open_url = True
    tabbed_browser_stubs[0].widget.tabs[0].is_private = True

    assert tabutils.switch_to_open_url(QUrl('https://github.com'),
                                       private=False) is None


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
