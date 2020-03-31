# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.misc.utilcmds."""

import logging

import pytest
from PyQt5.QtCore import QUrl

from qutebrowser.misc import utilcmds
from qutebrowser.api import cmdutils
from qutebrowser.utils import objreg


def test_repeat_command_initial(mocker, mode_manager):
    """Test repeat_command first-time behavior.

    If :repeat-command is called initially, it should err, because there's
    nothing to repeat.
    """
    objreg_mock = mocker.patch('qutebrowser.misc.utilcmds.objreg')
    objreg_mock.get.return_value = mode_manager
    with pytest.raises(cmdutils.CommandError,
                       match="You didn't do anything yet."):
        utilcmds.repeat_command(win_id=0)


def test_debug_log_level(mocker):
    """Test interactive log level changing."""
    formatter_mock = mocker.patch(
        'qutebrowser.misc.utilcmds.log.change_console_formatter')
    handler_mock = mocker.patch(
        'qutebrowser.misc.utilcmds.log.console_handler')
    utilcmds.debug_log_level(level='debug')
    formatter_mock.assert_called_with(logging.DEBUG)
    handler_mock.setLevel.assert_called_with(logging.DEBUG)


class FakeWindow:

    """Mock class for window_only."""

    def __init__(self, deleted=False):
        self.closed = False
        self.deleted = deleted

    def close(self):
        """Flag as closed."""
        self.closed = True


def test_window_only(mocker, monkeypatch):
    """Verify that window_only doesn't close the current or deleted windows."""
    test_windows = {0: FakeWindow(), 1: FakeWindow(True), 2: FakeWindow()}
    winreg_mock = mocker.patch('qutebrowser.misc.utilcmds.objreg')
    winreg_mock.window_registry = test_windows
    sip_mock = mocker.patch('qutebrowser.misc.utilcmds.sip')
    sip_mock.isdeleted.side_effect = lambda window: window.deleted
    utilcmds.window_only(current_win_id=0)
    assert not test_windows[0].closed
    assert not test_windows[1].closed
    assert test_windows[2].closed


@pytest.fixture
def tabbed_browser(stubs, win_registry):
    tb = stubs.TabbedBrowserStub()
    objreg.register('tabbed-browser', tb, scope='window', window=0)
    yield tb
    objreg.delete('tabbed-browser', scope='window', window=0)


def test_version(tabbed_browser, qapp):
    utilcmds.version(win_id=0)
    assert tabbed_browser.loaded_url == QUrl('qute://version/')
