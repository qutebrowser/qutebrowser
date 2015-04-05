# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Test signal debug output functions."""

import pytest

from qutebrowser.utils import debug


@pytest.fixture
def signal(stubs):
    """Fixture to provide a faked pyqtSignal."""
    return stubs.FakeSignal()


def test_signal_name(signal):
    """Test signal_name()."""
    assert debug.signal_name(signal) == 'fake'


def test_dbg_signal(signal):
    """Test dbg_signal()."""
    assert debug.dbg_signal(signal, [23, 42]) == 'fake(23, 42)'


def test_dbg_signal_eliding(signal):
    """Test eliding in dbg_signal()."""
    dbg_signal = debug.dbg_signal(signal, ['x' * 201])
    assert dbg_signal == "fake('{}\u2026)".format('x' * 198)


def test_dbg_signal_newline(signal):
    """Test dbg_signal() with a newline."""
    dbg_signal = debug.dbg_signal(signal, ['foo\nbar'])
    assert dbg_signal == r"fake('foo\nbar')"
