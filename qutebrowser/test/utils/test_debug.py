# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# pylint: disable=pointless-statement,no-member

"""Tests for qutebrowser.utils.debug."""

import unittest
from unittest import TestCase

from PyQt5.QtWidgets import QStyle, QFrame

import qutebrowser.utils.debug as debug


class QEnumKeyTests(TestCase):

    """Tests for qenum_key."""

    def test_no_metaobj(self):
        """Test with an enum with no metaobject."""
        with self.assertRaises(AttributeError):
            QStyle.PrimitiveElement.staticMetaObject
        key = debug.qenum_key(QStyle, QStyle.PE_PanelButtonCommand)
        self.assertEqual(key, 'PE_PanelButtonCommand')

    def test_metaobj(self):
        """Test with an enum with metaobject."""
        QFrame.staticMetaObject
        key = debug.qenum_key(QFrame, QFrame.Sunken)
        self.assertEqual(key, 'Sunken')


if __name__ == '__main__':
    unittest.main()
