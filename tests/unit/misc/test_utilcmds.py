# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

import contextlib
import logging
import pytest
import signal

_hunter_available = False
try:
    import hunter  # pylint: disable=unused-import
    _hunter_available = True
except ImportError:
    pass

from qutebrowser.misc import utilcmds as utilcmdsmod

from qutebrowser.commands import cmdexc


@contextlib.contextmanager
def _trapped_segv(handler):
    """Temporarily install given signal handler for SIGSEGV."""
    old_handler = signal.signal(signal.SIGSEGV, handler)
    yield
    signal.signal(signal.SIGSEGV, old_handler)


def test_debug_crash():
    """Verify that debug_crash crashes as intended."""
    with pytest.raises(Exception):
        utilcmdsmod.debug_crash(typ='exception')

    caught = False

    def _handler(num, frame):
        """Temporary handler for segfault."""
        nonlocal caught
        caught = num == signal.SIGSEGV

    with _trapped_segv(_handler):
        # since we handle the segfault, execution will continue and run into
        # the "Segfault failed (wat.)" Exception
        with pytest.raises(Exception) as excinfo:
            utilcmdsmod.debug_crash(typ='segfault')
    assert caught
    assert 'Segfault failed' in str(excinfo.value)


@pytest.mark.skipif(not _hunter_available, reason="hunter not available")
def test_debug_trace(mocker):
    """Check if hunter.trace is properly called."""
    hunter_mock = mocker.patch('qutebrowser.misc.utilcmds.hunter')
    utilcmdsmod.debug_trace(1)
    assert hunter_mock.trace.assert_called_with(1)

    hunter_mock.trace.side_effect = Exception
    with pytest.raises(Exception):
        utilcmdsmod.debug_trace()


def test_debug_trace_no_hunter(monkeypatch):
    """Test that an error is shown if debug_trace is called without hunter."""
    monkeypatch.setattr(utilcmdsmod, 'hunter', None)
    with pytest.raises(cmdexc.CommandError):
        utilcmdsmod.debug_trace()


class FakeModeMan:

    """ModeManager mock class for :repeat-command test.

    Attributes:
        mode: False
    """

    def __init__(self):
        self.mode = False


def test_repeat_command_initial(mocker):
    """Test repeat_command first-time behaviour.

    If :repeat-command is called initially, it should err, because there's
    nothing to repeat.
    """
    objreg_mock = mocker.patch('qutebrowser.misc.utilcmds.objreg')
    objreg_mock.get.return_value = FakeModeMan()
    with pytest.raises(cmdexc.CommandError):
        utilcmdsmod.repeat_command(win_id=0)


def test_debug_log_level(mocker):
    """Test interactive log level changing."""
    formatter_mock = mocker.patch(
        'qutebrowser.misc.utilcmds.log.change_console_formatter')
    handler_mock = mocker.patch(
        'qutebrowser.misc.utilcmds.log.console_handler')
    utilcmdsmod.debug_log_level(level='debug')
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
    utilcmdsmod.window_only(current_win_id=0)
    assert not test_windows[0].closed
    assert not test_windows[1].closed
    assert test_windows[2].closed
