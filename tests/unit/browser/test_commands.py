# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Test TabbedBrowser command dispatche."""

from unittest import mock

import pytest

from qutebrowser.browser import commands
from qutebrowser.completion.models import completionmodel
from qutebrowser.commands import cmdexc
from qutebrowser.mainwindow import tabbedbrowser, tabwidget
from qutebrowser.utils import objreg


class TestBuffer:
    """Test logic for :buffer in CommandDispatcher."""

    @pytest.fixture
    def tabbed_browser(self):
        """Simple tabbed browser mock that doesn't require winreg."""
        tabbed_browser = mock.create_autospec(tabbedbrowser.TabbedBrowser)
        tabbed_browser.widget = mock.create_autospec(tabwidget.TabWidget)
        yield tabbed_browser

    @pytest.fixture
    def app(self, stubs):
        """Simple tabbed browser mock that doesn't require winreg."""
        app = stubs.FakeQApplication()
        objreg.register('app', app)
        yield app
        objreg.delete('app')

    @mock.patch.object(commands.CommandDispatcher, 'openurl')
    def test_no_args_opens_page(self, openurl_mock, tabbed_browser):
        """When called with no args open a new page with a list of tabs."""
        uut = commands.CommandDispatcher(0, tabbed_browser)
        uut.buffer()
        openurl_mock.assert_called_once_with(
            "qute://tabs/", tab=True
        )

    @pytest.mark.parametrize("count, index, expect", [
        (8, None, "8"),
        (8, "0", "8"),
        (8, "2", "8"),
        (0, "2", "0"),
        (None, "2", "2"),
    ])
    @mock.patch.object(commands.CommandDispatcher, '_resolve_buffer_index')
    def test_runs_with_count_or_index(self, resolve_mock, tabbed_browser,
                                      count, index, expect):
        """Accept an index arg or a count, prefer count."""
        resolve_mock.return_value = (tabbed_browser, None)
        uut = commands.CommandDispatcher(0, tabbed_browser)
        uut.buffer(count=count, index=index)
        resolve_mock.assert_called_once_with(expect)

    @mock.patch.object(commands.CommandDispatcher, '_resolve_buffer_index')
    def test_window_raised(self, resolve_mock, tabbed_browser):
        """Test the resolved window and tab are presented to the user."""
        tab = mock.Mock()
        resolve_mock.return_value = (tabbed_browser, tab)
        uut = commands.CommandDispatcher(0, tabbed_browser)
        uut.buffer(0)

        # Raise the window, probably fragile.
        window = tabbed_browser.widget.window.return_value
        window.activateWindow.assert_called_once_with()
        window.raise_.assert_called_once_with()

        tabbed_browser.widget.setCurrentWidget.assert_called_once_with(tab)

    def test_tab_resolves(self, tabbed_browser_stubs):
        """Test the happy path of getting a fully specified index."""
        fake_tab = mock.Mock()
        tabbed_browser_stubs[0].widget.tabs = [
            fake_tab
        ]
        uut = commands.CommandDispatcher(0, None)
        tabbed_browser, tab = uut._resolve_buffer_index('0/1')
        assert tabbed_browser is tabbed_browser_stubs[0]
        assert tab is fake_tab

    def test_tab_resolves_with_no_winid(
            self, tabbed_browser_stubs, app, monkeypatch
    ):
        """Test resolving and index with no window specified."""
        fake_tab = mock.Mock()
        tabbed_browser_stubs[1].widget.tabs = [
            fake_tab
        ]
        window = mock.Mock()
        window.return_value.win_id = 1
        monkeypatch.setattr(app, 'activeWindow', window)

        uut = commands.CommandDispatcher(0, None)
        tabbed_browser, tab = uut._resolve_buffer_index('1')
        assert tabbed_browser is tabbed_browser_stubs[1]
        assert tab is fake_tab

    def test_tab_resolving_no_active_window(self, app, monkeypatch):
        """Ensure a failure to lookup the active window is handled."""
        window = mock.Mock()
        window.return_value = None
        monkeypatch.setattr(app, 'activeWindow', window)

        uut = commands.CommandDispatcher(0, None)
        with pytest.raises(cmdexc.CommandError) as err:
            uut._resolve_buffer_index('1')
        assert str(err).endswith(
            "No window specified and couldn't find active window!"
        )

    @pytest.mark.parametrize("winid", [
        -1,
        # tabbed_browser_stubs fills in 0 and 1
        2,
        123,
    ])
    def test_tab_resolving_no_matching_window(self, winid,
                                              tabbed_browser_stubs):
        """Ensure getting passed and out-of range winid is handled."""
        uut = commands.CommandDispatcher(0, None)
        with pytest.raises(cmdexc.CommandError) as err:
            uut._resolve_buffer_index('{}/1'.format(winid))
        assert str(err).endswith(
            "There's no window with id {}!".format(winid)
        )

    @pytest.mark.parametrize("tabid", [
        -1,
        0,
        2,
        123,
    ])
    def test_tab_resolving_no_matching_tab(self, tabid,
                                           tabbed_browser_stubs):
        """Ensure a getting passed and out-of range winid is handled."""
        tabbed_browser_stubs[0].widget.tabs = [
            mock.Mock()
        ]
        uut = commands.CommandDispatcher(0, None)
        with pytest.raises(cmdexc.CommandError) as err:
            uut._resolve_buffer_index('0/{}'.format(tabid))
        assert str(err).endswith(
            "There's no tab with index {}!".format(tabid)
        )

    @pytest.mark.parametrize("arg", [
        "foo",
        "o/1",
        "0/l",
        "0/1/2",
        "ö",
    ])
    @mock.patch.object(commands.miscmodels, 'buffer')
    def test_tab_resolving_bad_string_args(self, buffer_mock, arg):
        """Make sure string args that aren't int/int go to completion."""
        model = mock.create_autospec(completionmodel.CompletionModel)
        # fail them so we don't have to mock the rest of the code in the
        # function
        model.count.return_value = 0
        buffer_mock.return_value = model

        uut = commands.CommandDispatcher(0, None)
        with pytest.raises(cmdexc.CommandError) as err:
            uut._resolve_buffer_index(arg)

        model.set_pattern.assert_called_once_with(arg)
        assert str(err).endswith("No matching tab for: {}".format(arg))

    @mock.patch.object(commands.miscmodels, 'buffer')
    def test_tab_resolving_good_string_arg(self, buffer_mock,
                                           tabbed_browser_stubs):
        """Make sure the result of the completion is handled right."""
        fake_tab = mock.Mock()
        tabbed_browser_stubs[0].widget.tabs = [
            fake_tab
        ]
        model = mock.create_autospec(completionmodel.CompletionModel)
        model.count.return_value = 10
        model.first_item.return_value = 'relevant match'
        model.data.return_value = '0/1'
        buffer_mock.return_value = model

        uut = commands.CommandDispatcher(0, None)
        tabbed_browser, tab = uut._resolve_buffer_index('foo')

        model.set_pattern.assert_called_once_with('foo')
        model.first_item.assert_called_once_with()
        model.data.assert_called_once_with('relevant match')

        assert tabbed_browser is tabbed_browser_stubs[0]
        assert tab is fake_tab
