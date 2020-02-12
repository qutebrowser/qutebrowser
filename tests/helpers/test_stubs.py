# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


"""Test test stubs."""

from unittest import mock

import pytest


@pytest.fixture
def timer(stubs):
    return stubs.FakeTimer()


def test_timeout(timer):
    """Test whether timeout calls the functions."""
    func = mock.Mock()
    func2 = mock.Mock()
    timer.timeout.connect(func)
    timer.timeout.connect(func2)
    func.assert_not_called()
    func2.assert_not_called()
    timer.timeout.emit()
    func.assert_called_once_with()
    func2.assert_called_once_with()


def test_disconnect_all(timer):
    """Test disconnect without arguments."""
    func = mock.Mock()
    timer.timeout.connect(func)
    timer.timeout.disconnect()
    timer.timeout.emit()
    func.assert_not_called()


def test_disconnect_one(timer):
    """Test disconnect with a single argument."""
    func = mock.Mock()
    timer.timeout.connect(func)
    timer.timeout.disconnect(func)
    timer.timeout.emit()
    func.assert_not_called()


def test_disconnect_all_invalid(timer):
    """Test disconnecting with no connections."""
    with pytest.raises(TypeError):
        timer.timeout.disconnect()


def test_disconnect_one_invalid(timer):
    """Test disconnecting with an invalid connection."""
    func1 = mock.Mock()
    func2 = mock.Mock()
    timer.timeout.connect(func1)
    with pytest.raises(TypeError):
        timer.timeout.disconnect(func2)
    func1.assert_not_called()
    func2.assert_not_called()
    timer.timeout.emit()
    func1.assert_called_once_with()


def test_singleshot(timer):
    """Test setting singleShot."""
    assert not timer.isSingleShot()
    timer.setSingleShot(True)
    assert timer.isSingleShot()
    timer.start()
    assert timer.isActive()
    timer.timeout.emit()
    assert not timer.isActive()


def test_active(timer):
    """Test isActive."""
    assert not timer.isActive()
    timer.start()
    assert timer.isActive()
    timer.stop()
    assert not timer.isActive()


def test_interval(timer):
    """Test setting an interval."""
    assert timer.interval() == 0
    timer.setInterval(1000)
    assert timer.interval() == 1000
