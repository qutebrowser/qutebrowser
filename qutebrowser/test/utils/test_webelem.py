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

# pylint: disable=missing-docstring,invalid-name

"""Tests for the webelement utils."""

import unittest
from unittest import TestCase
from unittest.mock import Mock

from PyQt5.QtCore import QRect, QPoint

import qutebrowser.utils.webelem as webelem


class FakeWebElement:

    def __init__(self, geometry=None, frame=None, null=False):
        self.geometry = Mock(return_value=geometry)
        self.webFrame = Mock(return_value=frame)
        self.isNull = Mock(return_value=null)


class FakeWebFrame:

    def __init__(self, geometry, scroll):
        self.geometry = Mock(return_value=geometry)
        self.scrollPosition = Mock(return_value=scroll)


class IsVisibleInvalidTests(TestCase):

    def setUp(self):
        self.frame = FakeWebFrame(QRect(0, 0, 100, 100), QPoint(0, 0))

    def test_nullelem(self):
        elem = FakeWebElement(null=True)
        with self.assertRaises(ValueError):
            webelem.is_visible(elem)
        elem.isNull.assert_called_once_with()
        self.assertFalse(elem.geometry.called)
        self.assertFalse(elem.webFrame.called)

    def test_invalid_invisible(self):
        elem = FakeWebElement(geometry=QRect(0, 0, 0, 0))
        self.assertFalse(elem.geometry().isValid())
        self.assertEqual(elem.geometry().x(), 0)
        self.assertFalse(webelem.is_visible(elem))

    def test_invalid_visible(self):
        elem = FakeWebElement(geometry=QRect(10, 10, 0, 0))
        self.assertFalse(elem.geometry().isValid())
        self.assertTrue(webelem.is_visible(elem, self.frame))


class IsVisibleScrollTests(TestCase):

    def setUp(self):
        self.frame = FakeWebFrame(QRect(0, 0, 100, 100), QPoint(10, 10))

    def test_invisible(self):
        elem = FakeWebElement(geometry=QRect(9, 9, 0, 0))
        self.assertFalse(webelem.is_visible(elem, self.frame))

    def test_visible(self):
        elem = FakeWebElement(geometry=QRect(10, 10, 0, 0))
        self.assertTrue(webelem.is_visible(elem, self.frame))


class JavascriptEscapeTests(TestCase):

    def test_escape(self):
        self.assertEqual(
            webelem.javascript_escape('one\\two\nthree\tfour\'five"six'),
            r"""one\\two\nthree\tfour\'five\"six""")


if __name__ == '__main__':
    unittest.main()
