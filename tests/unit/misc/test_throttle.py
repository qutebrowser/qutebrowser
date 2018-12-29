# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2018 Jay Kamat <jaygkamat@gmail.com>:
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

# False-positives

"""Tests for qutebrowser.misc.throttle."""

from unittest import mock

from qutebrowser.misc.throttle import throttle
from qutebrowser.utils import usertypes


def test_throttle_imm(qtbot):
    func = mock.Mock()
    throttled_func = throttle(100)(func)
    throttled_func("foo")
    throttled_func("foo")
    func.assert_called_once_with("foo")


def test_throttle_delay(qtbot):
    func = mock.Mock()
    throttled_func = throttle(100)(func)
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()

    t = usertypes.Timer()
    with qtbot.waitSignal(t.timeout, timeout=500):
        t.start(200)

    func.assert_called_once_with("bar")


def test_throttle_delay_imm_delay(qtbot):
    func = mock.Mock()
    throttled_func = throttle(100)(func)
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()

    t = usertypes.Timer()
    with qtbot.waitSignal(t.timeout, timeout=500):
        t.start(400)

    func.assert_called_once_with("bar")
    func.reset_mock()
    throttled_func("baz")
    throttled_func("baz")
    throttled_func("bop")

    func.assert_called_once_with("baz")
    func.reset_mock()

    t = usertypes.Timer()
    with qtbot.waitSignal(t.timeout, timeout=500):
        t.start(200)

    func.assert_called_once_with("bop")


def test_throttle_delay_delay(qtbot):
    func = mock.Mock()
    throttled_func = throttle(100)(func)
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("foo")
    throttled_func("bar")
    func.assert_called_once_with("foo")
    func.reset_mock()

    t = usertypes.Timer()
    with qtbot.waitSignal(t.timeout, timeout=500):
        t.start(150)

    func.assert_called_once_with("bar")
    func.reset_mock()
    throttled_func("baz")
    throttled_func("baz")
    throttled_func("bop")

    t = usertypes.Timer()
    with qtbot.waitSignal(t.timeout, timeout=500):
        t.start(200)

    func.assert_called_once_with("bop")
    func.reset_mock()
