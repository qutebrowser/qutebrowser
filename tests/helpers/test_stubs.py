# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
