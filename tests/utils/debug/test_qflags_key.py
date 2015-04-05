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

"""Tests for qutebrowser.utils.debug.qflags_key.

https://github.com/The-Compiler/qutebrowser/issues/42
"""

import pytest

from PyQt5.QtCore import Qt
from qutebrowser.utils import debug


fixme = pytest.mark.xfail(reason="See issue #42", raises=AssertionError)


@fixme
def test_single():
    """Test with single value."""
    flags = debug.qflags_key(Qt, Qt.AlignTop)
    assert flags == 'AlignTop'


@fixme
def test_multiple():
    """Test with multiple values."""
    flags = debug.qflags_key(Qt, Qt.AlignLeft | Qt.AlignTop)
    assert flags == 'AlignLeft|AlignTop'


def test_combined():
    """Test with a combined value."""
    flags = debug.qflags_key(Qt, Qt.AlignCenter)
    assert flags == 'AlignHCenter|AlignVCenter'


@fixme
def test_add_base():
    """Test with add_base=True."""
    flags = debug.qflags_key(Qt, Qt.AlignTop, add_base=True)
    assert flags == 'Qt.AlignTop'


def test_int_noklass():
    """Test passing an int without explicit klass given."""
    with pytest.raises(TypeError):
        debug.qflags_key(Qt, 42)


@fixme
def test_int():
    """Test passing an int with explicit klass given."""
    flags = debug.qflags_key(Qt, 0x0021, klass=Qt.Alignment)
    assert flags == 'AlignLeft|AlignTop'


def test_unknown():
    """Test passing an unknown value."""
    flags = debug.qflags_key(Qt, 0x1100, klass=Qt.Alignment)
    assert flags == '0x0100|0x1000'
