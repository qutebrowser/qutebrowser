# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018-2019 Jay Kamat <jaygkamat@gmail.com>:
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

"""Tests for qutebrowser.misc.throttle."""

from unittest import mock

import sip
import pytest
from PyQt5.QtCore import QObject

from qutebrowser.misc import throttle


@pytest.fixture
def func():
    return mock.Mock(spec=[])


@pytest.fixture
def throttled_func(func):
    return throttle.Throttle(func, 100)


def test_immediate(throttled_func, func, qapp):
    throttled_func("foo")
    throttled_func("foo")
    func.assert_called_once_with("foo")


def test_immediate_kwargs(throttled_func, func, qapp):
    throttled_func(foo="bar")
    throttled_func(foo="bar")
    func.assert_called_once_with(foo="bar")


def test_delayed(throttled_func, func, qtbot):
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()

    qtbot.wait(200)

    func.assert_called_once_with("bar")


def test_delayed_immediate_delayed(throttled_func, func, qtbot):
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()

    qtbot.wait(400)

    func.assert_called_once_with("bar")
    func.reset_mock()
    throttled_func("baz")
    throttled_func("baz")
    throttled_func("bop")

    func.assert_called_once_with("baz")
    func.reset_mock()

    qtbot.wait(200)

    func.assert_called_once_with("bop")


def test_delayed_delayed(throttled_func, func, qtbot):
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()

    qtbot.wait(150)

    func.assert_called_once_with("bar")
    func.reset_mock()
    throttled_func("baz")
    throttled_func("baz")
    throttled_func("bop")

    qtbot.wait(200)

    func.assert_called_once_with("bop")
    func.reset_mock()


def test_cancel(throttled_func, func, qtbot):
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()
    throttled_func.cancel()

    qtbot.wait(150)

    func.assert_not_called()
    func.reset_mock()


def test_set(func, qtbot):
    throttled_func = throttle.Throttle(func, 100)
    throttled_func.set_delay(100)
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()

    qtbot.wait(150)

    func.assert_called_once_with("bar")
    func.reset_mock()


def test_deleted_object(qtbot):
    class Obj(QObject):

        def func(self):
            self.setObjectName("test")

    obj = Obj()

    throttled_func = throttle.Throttle(obj.func, 100, parent=obj)
    throttled_func()
    throttled_func()

    sip.delete(obj)

    qtbot.wait(150)
