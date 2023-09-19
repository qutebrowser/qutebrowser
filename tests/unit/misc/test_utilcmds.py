# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.misc.utilcmds."""

import pytest
from qutebrowser.qt.core import QUrl

from qutebrowser.misc import utilcmds
from qutebrowser.api import cmdutils
from qutebrowser.utils import objreg


def test_cmd_repeat_last_initial(mocker, mode_manager):
    """Test repeat_command first-time behavior.

    If :cmd-repeat-last is called initially, it should err, because there's
    nothing to repeat.
    """
    objreg_mock = mocker.patch('qutebrowser.misc.utilcmds.objreg')
    objreg_mock.get.return_value = mode_manager
    with pytest.raises(cmdutils.CommandError,
                       match="You didn't do anything yet."):
        utilcmds.cmd_repeat_last(win_id=0)


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
