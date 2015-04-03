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

"""Tests for qutebrowser.utils.debug."""

import pytest

from PyQt5.QtWidgets import QStyle, QFrame

from qutebrowser.utils import debug


def test_no_metaobj():
    """Test with an enum with no meta-object."""

    with pytest.raises(AttributeError):
        # Make sure it doesn't have a meta object
        # pylint: disable=pointless-statement,no-member
        QStyle.PrimitiveElement.staticMetaObject

    key = debug.qenum_key(QStyle, QStyle.PE_PanelButtonCommand)
    assert key == 'PE_PanelButtonCommand'


def test_metaobj():
    """Test with an enum with meta-object."""

    # pylint: disable=pointless-statement
    QFrame.staticMetaObject  # make sure it has a meta-object

    key = debug.qenum_key(QFrame, QFrame.Sunken)
    assert key == 'Sunken'


def test_add_base():
    """Test with add_base=True."""

    key = debug.qenum_key(QFrame, QFrame.Sunken, add_base=True)
    assert key == 'QFrame.Sunken'
