# SPDX-FileCopyrightText: Freya Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for the qutebrowser.app module."""

from unittest import mock

from qutebrowser.qt.core import QBuffer, QUrl

from qutebrowser.misc import objects
from qutebrowser.mainwindow import mainwindow
from qutebrowser import app


def test_on_focus_changed_issue1484(monkeypatch, qapp, caplog):
    """Check what happens when on_focus_changed is called with wrong args.

    For some reason, Qt sometimes calls on_focus_changed() with a QBuffer as
    argument. Let's make sure we handle that gracefully.
    """
    monkeypatch.setattr(objects, 'qapp', qapp)

    buf = QBuffer()
    app.on_focus_changed(buf, buf)

    expected = "on_focus_changed called with non-QWidget {!r}".format(buf)
    assert caplog.messages == [expected]


def test_open_url_switches_to_existing_tab(monkeypatch, config_stub,
                                           tabbed_browser_stubs, fake_web_tab):
    """With the option on, open_url switches and returns the existing window."""
    config_stub.val.tabs.switch_to_open_url = True

    url = QUrl('http://example.com/')
    tab = fake_web_tab(url, 'Example')
    # Real browser tabs report is_private as None, not False. Pin it so this
    # exercises the same None-vs-bool comparison the IPC entry point hits.
    tab.is_private = None
    tabbed_browser_stubs[0].widget.tabs = [tab]
    existing_window = mock.Mock()
    tabbed_browser_stubs[0].widget.setWindow(existing_window)

    new_window = mock.Mock()
    monkeypatch.setattr(mainwindow, 'get_window', lambda **kwargs: new_window)

    result = app.open_url(url, target='tab', via_ipc=False)

    assert result is existing_window
    assert existing_window.activateWindow.called
    assert not new_window.tabbed_browser.tabopen.called


def test_open_url_no_switch_when_disabled(monkeypatch, config_stub,
                                          tabbed_browser_stubs, fake_web_tab):
    """With the option off, open_url opens normally even with a matching tab."""
    config_stub.val.tabs.switch_to_open_url = False

    url = QUrl('http://example.com/')
    tabbed_browser_stubs[0].widget.tabs = [fake_web_tab(url, 'Example')]
    existing_window = mock.Mock()
    tabbed_browser_stubs[0].widget.setWindow(existing_window)

    new_window = mock.Mock()
    monkeypatch.setattr(mainwindow, 'get_window', lambda **kwargs: new_window)

    result = app.open_url(url, target='tab', via_ipc=False)

    assert result is new_window
    assert new_window.tabbed_browser.tabopen.called
    assert not existing_window.activateWindow.called
