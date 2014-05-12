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
from PyQt5.QtWebKit import QWebElement

import qutebrowser.utils.webelem as webelem


class FakeWebElement:

    def __init__(self, geometry=None, frame=None, null=False, visibility='',
                 display=''):
        self.geometry = Mock(return_value=geometry)
        self.webFrame = Mock(return_value=frame)
        self.isNull = Mock(return_value=null)
        self._visibility = visibility
        self._display = display

    def styleProperty(self, name, strategy):
        if strategy != QWebElement.ComputedStyle:
            raise ValueError("styleProperty called with strategy != "
                             "ComputedStyle ({})!".format(strategy))
        if name == 'visibility':
            return self._visibility
        elif name == 'display':
            return self._display
        else:
            raise ValueError("styleProperty called with unknown name "
                             "'{}'".format(name))


class FakeWebFrame:

    def __init__(self, geometry, scroll, parent=None):
        self.geometry = Mock(return_value=geometry)
        self.scrollPosition = Mock(return_value=scroll)
        self.parentFrame = Mock(return_value=parent)


class IsVisibleInvalidTests(TestCase):

    def setUp(self):
        self.frame = FakeWebFrame(QRect(0, 0, 100, 100), scroll=QPoint(0, 0))

    def test_nullelem(self):
        elem = FakeWebElement(null=True)
        with self.assertRaises(ValueError):
            webelem.is_visible(elem, self.frame)
        elem.isNull.assert_called_once_with()
        self.assertFalse(elem.geometry.called)
        self.assertFalse(elem.webFrame.called)

    def test_invalid_invisible(self):
        elem = FakeWebElement(geometry=QRect(0, 0, 0, 0), frame=self.frame)
        self.assertFalse(elem.geometry().isValid())
        self.assertEqual(elem.geometry().x(), 0)
        self.assertFalse(webelem.is_visible(elem, self.frame))

    def test_invalid_visible(self):
        elem = FakeWebElement(geometry=QRect(10, 10, 0, 0), frame=self.frame)
        self.assertFalse(elem.geometry().isValid())
        self.assertTrue(webelem.is_visible(elem, self.frame))


class IsVisibleScrollTests(TestCase):

    def setUp(self):
        self.frame = FakeWebFrame(QRect(0, 0, 100, 100), scroll=QPoint(10, 10))

    def test_invisible(self):
        elem = FakeWebElement(geometry=QRect(5, 5, 4, 4), frame=self.frame)
        self.assertFalse(webelem.is_visible(elem, self.frame))

    def test_visible(self):
        elem = FakeWebElement(geometry=QRect(10, 10, 1, 1), frame=self.frame)
        self.assertTrue(webelem.is_visible(elem, self.frame))


class IsVisibleCssTests(TestCase):

    def setUp(self):
        self.frame = FakeWebFrame(QRect(0, 0, 100, 100), scroll=QPoint(0, 0))

    def test_visibility_visible(self):
        elem = FakeWebElement(geometry=QRect(0, 0, 10, 10), frame=self.frame,
                              visibility='visible')
        self.assertTrue(webelem.is_visible(elem, self.frame))

    def test_visibility_hidden(self):
        elem = FakeWebElement(geometry=QRect(0, 0, 10, 10), frame=self.frame,
                              visibility='hidden')
        self.assertFalse(webelem.is_visible(elem, self.frame))

    def test_display_inline(self):
        elem = FakeWebElement(geometry=QRect(0, 0, 10, 10), frame=self.frame,
                              display='inline')
        self.assertTrue(webelem.is_visible(elem, self.frame))

    def test_display_none(self):
        elem = FakeWebElement(geometry=QRect(0, 0, 10, 10), frame=self.frame,
                              display='none')
        self.assertFalse(webelem.is_visible(elem, self.frame))


class JavascriptEscapeTests(TestCase):

    def test_escape(self):
        self.assertEqual(
            webelem.javascript_escape('one\\two\nthree\tfour\'five"six'),
            r"""one\\two\nthree\tfour\'five\"six""")


if __name__ == '__main__':
    unittest.main()
