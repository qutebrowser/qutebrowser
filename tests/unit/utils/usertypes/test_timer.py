# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for Timer."""

import pytest
from qutebrowser.qt.core import QObject

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
