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

"""Tests for Timer."""

import pytest
from PyQt5.QtCore import QObject

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
    with qtbot.waitSignal(t.timeout, timeout=3000):
        t.start(200)


def test_timeout_set_interval(qtbot):
    """Make sure the timer works with setInterval()."""
    t = usertypes.Timer()
    with qtbot.waitSignal(t.timeout, timeout=3000):
        t.setInterval(200)
        t.start()
