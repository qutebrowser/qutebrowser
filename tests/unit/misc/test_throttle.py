# SPDX-FileCopyrightText: Jay Kamat <jaygkamat@gmail.com>:
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for qutebrowser.misc.throttle."""

from unittest import mock

from qutebrowser.qt import sip
import pytest
from qutebrowser.qt.core import QObject

from helpers import testutils
from qutebrowser.misc import throttle


DELAY = 500 if testutils.ON_CI else 100


@pytest.fixture
def func():
    return mock.Mock(spec=[])


@pytest.fixture
def throttled(func):
    return throttle.Throttle(func, DELAY)


def test_immediate(throttled, func, qapp):
    throttled("foo")
    throttled("foo")
    func.assert_called_once_with("foo")


def test_immediate_kwargs(throttled, func, qapp):
    throttled(foo="bar")
    throttled(foo="bar")
    func.assert_called_once_with(foo="bar")


def test_delayed(throttled, func, qtbot):
    throttled("foo")
    throttled("foo")
    throttled("foo")
    throttled("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()

    qtbot.wait(2 * DELAY)

    func.assert_called_once_with("bar")


def test_delayed_immediate_delayed(throttled, func, qtbot):
    throttled("foo")
    throttled("foo")
    throttled("foo")
    throttled("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()

    qtbot.wait(4 * DELAY)

    func.assert_called_once_with("bar")
    func.reset_mock()
    throttled("baz")
    throttled("baz")
    throttled("bop")

    func.assert_called_once_with("baz")
    func.reset_mock()

    qtbot.wait(2 * DELAY)

    func.assert_called_once_with("bop")


def test_delayed_delayed(throttled, func, qtbot):
    throttled("foo")
    throttled("foo")
    throttled("foo")
    throttled("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()

    qtbot.wait(int(1.5 * DELAY))

    func.assert_called_once_with("bar")
    func.reset_mock()
    throttled("baz")
    throttled("baz")
    throttled("bop")

    qtbot.wait(2 * DELAY)

    func.assert_called_once_with("bop")
    func.reset_mock()


def test_cancel(throttled, func, qtbot):
    throttled("foo")
    throttled("foo")
    throttled("foo")
    throttled("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()
    throttled.cancel()

    qtbot.wait(int(1.5 * DELAY))

    func.assert_not_called()
    func.reset_mock()


def test_set(func, qtbot):
    throttled = throttle.Throttle(func, DELAY)
    throttled.set_delay(DELAY)
    throttled("foo")
    throttled("foo")
    throttled("foo")
    throttled("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()

    qtbot.wait(int(1.5 * DELAY))

    func.assert_called_once_with("bar")
    func.reset_mock()


def test_deleted_object(qtbot):
    class Obj(QObject):

        def func(self):
            self.setObjectName("test")

    obj = Obj()

    throttled = throttle.Throttle(obj.func, DELAY, parent=obj)
    throttled()
    throttled()

    sip.delete(obj)

    qtbot.wait(int(1.5 * DELAY))
