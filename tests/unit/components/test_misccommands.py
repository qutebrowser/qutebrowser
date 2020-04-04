# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Tests for qutebrowser.components.misccommands."""

import signal
import contextlib
import time

import pytest

from qutebrowser.api import cmdutils
from qutebrowser.utils import utils
from qutebrowser.components import misccommands


@contextlib.contextmanager
def _trapped_segv(handler):
    """Temporarily install given signal handler for SIGSEGV."""
    old_handler = signal.signal(signal.SIGSEGV, handler)
    yield
    if old_handler is not None:
        signal.signal(signal.SIGSEGV, old_handler)


def test_debug_crash_exception():
    """Verify that debug_crash crashes as intended."""
    with pytest.raises(Exception, match="Forced crash"):
        misccommands.debug_crash(typ='exception')


@pytest.mark.skipif(utils.is_windows,
                    reason="current CPython/win can't recover from SIGSEGV")
def test_debug_crash_segfault():
    """Verify that debug_crash crashes as intended."""
    caught = False

    def _handler(num, frame):
        """Temporary handler for segfault."""
        nonlocal caught
        caught = num == signal.SIGSEGV

    with _trapped_segv(_handler):
        # since we handle the segfault, execution will continue and run into
        # the "Segfault failed (wat.)" Exception
        with pytest.raises(Exception, match="Segfault failed"):
            misccommands.debug_crash(typ='segfault')
        time.sleep(0.001)
    assert caught


def test_debug_trace(mocker):
    """Check if hunter.trace is properly called."""
    # but only if hunter is available
    pytest.importorskip('hunter')
    hunter_mock = mocker.patch.object(misccommands, 'hunter')
    misccommands.debug_trace(1)
    hunter_mock.trace.assert_called_with(1)


def test_debug_trace_exception(mocker):
    """Check that exceptions thrown by hunter.trace are handled."""
    def _mock_exception():
        """Side effect for testing debug_trace's reraise."""
        raise Exception('message')

    hunter_mock = mocker.patch.object(misccommands, 'hunter')
    hunter_mock.trace.side_effect = _mock_exception
    with pytest.raises(cmdutils.CommandError, match='Exception: message'):
        misccommands.debug_trace()


def test_debug_trace_no_hunter(monkeypatch):
    """Test that an error is shown if debug_trace is called without hunter."""
    monkeypatch.setattr(misccommands, 'hunter', None)
    with pytest.raises(cmdutils.CommandError, match="You need to install "
                       "'hunter' to use this command!"):
        misccommands.debug_trace()
