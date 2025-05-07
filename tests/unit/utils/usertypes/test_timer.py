# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for Timer."""

import logging
import fnmatch

import pytest
import pytest_mock
from qutebrowser.qt.core import QObject, QTimer
from qutebrowser.qt.widgets import QApplication

from qutebrowser.utils import usertypes


class Parent(QObject):

    """Class for test_parent()."""


def test_parent():
    """Make sure the parent is set correctly."""
    parent = Parent()
    t = usertypes.Timer(parent)
    assert t.parent() is parent


def test_named():
    """Make sure the name is set correctly."""
    t = usertypes.Timer(name='foobar')
    assert t._name == 'foobar'
    assert t.objectName() == 'foobar'
    assert repr(t) == "<qutebrowser.utils.usertypes.Timer name='foobar'>"


def test_unnamed():
    """Make sure an unnamed Timer is named correctly."""
    t = usertypes.Timer()
    assert not t.objectName()
    assert t._name == 'unnamed'
    assert repr(t) == "<qutebrowser.utils.usertypes.Timer name='unnamed'>"


def test_set_interval_overflow():
    """Make sure setInterval raises OverflowError with very big numbers."""
    t = usertypes.Timer()
    with pytest.raises(OverflowError):
        t.setInterval(2 ** 64)


def test_start_overflow():
    """Make sure start raises OverflowError with very big numbers."""
    t = usertypes.Timer()
    with pytest.raises(OverflowError):
        t.start(2 ** 64)


def test_timeout_start(qtbot):
    """Make sure the timer works with start()."""
    t = usertypes.Timer()
    with qtbot.wait_signal(t.timeout, timeout=3000):
        t.start(200)


def test_timeout_set_interval(qtbot):
    """Make sure the timer works with setInterval()."""
    t = usertypes.Timer()
    with qtbot.wait_signal(t.timeout, timeout=3000):
        t.setInterval(200)
        t.start()


@pytest.fixture
def time_mock(qapp: QApplication, mocker: pytest_mock.MockerFixture) -> None:
    """Patch time.monotonic() to return a fixed value."""
    # Check if there are any stray timers still alive.
    # If previous tests didn't clean up a QApplication-wide QTimer correctly, this
    # will point us at the issue instead of test_early_timeout_check getting flaky
    # because of it.
    assert not qapp.findChildren(QTimer)
    return mocker.patch("time.monotonic", autospec=True)


@pytest.mark.parametrize(
    "elapsed_ms, expected",
    [
        (0, False),
        (1, False),
        (600, True),
        (999, True),
        (1000, True),
    ],
)
def test_early_timeout_check(time_mock, elapsed_ms, expected):
    t = usertypes.Timer()
    t.setInterval(1000)  # anything long enough to not actually fire
    time_mock.return_value = 0  # assigned to _start_time in start()
    t.start()
    time_mock.return_value = elapsed_ms / 1000  # used for `elapsed`

    assert t.check_timeout_validity() is expected

    t.stop()


def test_early_timeout_handler(qtbot, time_mock, caplog):
    t = usertypes.Timer(name="t")
    t.setInterval(3)
    t.setSingleShot(True)
    time_mock.return_value = 0
    with caplog.at_level(logging.WARNING):
        with qtbot.wait_signal(t.timeout, timeout=10):
            t.start()
            time_mock.return_value = 1 / 1000

        assert len(caplog.messages) == 1
        assert fnmatch.fnmatch(
            caplog.messages[-1],
            "Timer t (id *) triggered too early: interval 3 but only 0.001s passed",
        )


def test_early_manual_fire(qtbot, time_mock, caplog):
    """Same as above but start() never gets called."""
    t = usertypes.Timer(name="t")
    t.setInterval(3)
    t.setSingleShot(True)
    time_mock.return_value = 0
    with caplog.at_level(logging.WARNING):
        with qtbot.wait_signal(t.timeout, timeout=10):
            t.timeout.emit()
            time_mock.return_value = 1 / 1000

        assert len(caplog.messages) == 0
        assert t.check_timeout_validity()
