# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

"""Tests for the webelement utils."""

import unittest

from PyQt5.QtCore import QRect, QPoint

import qutebrowser.utils.webelem as webelem
from qutebrowser.test.stubs import (FakeWebElement, FakeWebFrame,
                                    FakeChildrenFrame)


class IsVisibleInvalidTests(unittest.TestCase):

    """Tests for is_visible with invalid elements.

    Attributes:
        frame: The FakeWebFrame we're using to test.
    """

    def setUp(self):
        self.frame = FakeWebFrame(QRect(0, 0, 100, 100))

    def test_nullelem(self):
        """Passing an element with isNull() == True.

        geometry() and webFrame() should not be called, and ValueError should
        be raised.
        """
        elem = FakeWebElement(null=True)
        with self.assertRaises(ValueError):
            webelem.is_visible(elem, self.frame)
        elem.isNull.assert_called_once_with()
        self.assertFalse(elem.geometry.called)
        self.assertFalse(elem.webFrame.called)

    def test_invalid_invisible(self):
        """Test elements with an invalid geometry which are invisible."""
        elem = FakeWebElement(QRect(0, 0, 0, 0), self.frame)
        self.assertFalse(elem.geometry().isValid())
        self.assertEqual(elem.geometry().x(), 0)
        self.assertFalse(webelem.is_visible(elem, self.frame))

    def test_invalid_visible(self):
        """Test elements with an invalid geometry which are visible.

        This seems to happen sometimes in the real world, with real elements
        which *are* visible, but don't have a valid geometry.
        """
        elem = FakeWebElement(QRect(10, 10, 0, 0), self.frame)
        self.assertFalse(elem.geometry().isValid())
        self.assertTrue(webelem.is_visible(elem, self.frame))


class IsVisibleScrollTests(unittest.TestCase):

    """Tests for is_visible when the frame is scrolled.

    Attributes:
        frame: The FakeWebFrame we're using to test.
    """

    def setUp(self):
        self.frame = FakeWebFrame(QRect(0, 0, 100, 100), scroll=QPoint(10, 10))

    def test_invisible(self):
        """Test elements which should be invisible due to scrolling."""
        elem = FakeWebElement(QRect(5, 5, 4, 4), self.frame)
        self.assertFalse(webelem.is_visible(elem, self.frame))

    def test_visible(self):
        """Test elements which still should be visible after scrolling."""
        elem = FakeWebElement(QRect(10, 10, 1, 1), self.frame)
        self.assertTrue(webelem.is_visible(elem, self.frame))


class IsVisibleCssTests(unittest.TestCase):

    """Tests for is_visible with CSS attributes.

    Attributes:
        frame: The FakeWebFrame we're using to test.
    """

    def setUp(self):
        self.frame = FakeWebFrame(QRect(0, 0, 100, 100))

    def test_visibility_visible(self):
        """Check that elements with "visibility = visible" are visible."""
        elem = FakeWebElement(QRect(0, 0, 10, 10), self.frame,
                              visibility='visible')
        self.assertTrue(webelem.is_visible(elem, self.frame))

    def test_visibility_hidden(self):
        """Check that elements with "visibility = hidden" are not visible."""
        elem = FakeWebElement(QRect(0, 0, 10, 10), self.frame,
                              visibility='hidden')
        self.assertFalse(webelem.is_visible(elem, self.frame))

    def test_display_inline(self):
        """Check that elements with "display = inline" are visible."""
        elem = FakeWebElement(QRect(0, 0, 10, 10), self.frame,
                              display='inline')
        self.assertTrue(webelem.is_visible(elem, self.frame))

    def test_display_none(self):
        """Check that elements with "display = none" are not visible."""
        elem = FakeWebElement(QRect(0, 0, 10, 10), self.frame, display='none')
        self.assertFalse(webelem.is_visible(elem, self.frame))


class IsVisibleIframeTests(unittest.TestCase):

    """Tests for is_visible with a child frame.

    Attributes:
        frame: The FakeWebFrame we're using to test.
        iframe: The iframe inside frame.
        elem1-elem4: FakeWebElements to test.
    """

    def setUp(self):
        """Set up this base situation
              0, 0                         300, 0
               ##############################
               #                            #
          0,10 # iframe  100,10             #
               #**********                  #
               #*e       * elem1: 0, 0 in iframe (visible)
               #*        *                  #
               #* e      * elem2: 20,90 in iframe (visible)
               #**********                  #
         0,110 #.        .100,110           #
               #.        .                  #
               #. e      . elem3: 20,150 in iframe (not visible)
               #..........                  #
               #     e     elem4: 30, 180 in main frame (visible)
               #                            #
               #          frame             #
               ##############################
             300, 0                         300, 300
        """
        self.frame = FakeWebFrame(QRect(0, 0, 300, 300))
        self.iframe = FakeWebFrame(QRect(0, 10, 100, 100), parent=self.frame)
        self.elem1 = FakeWebElement(QRect(0, 0, 10, 10), self.iframe)
        self.elem2 = FakeWebElement(QRect(20, 90, 10, 10), self.iframe)
        self.elem3 = FakeWebElement(QRect(20, 150, 10, 10), self.iframe)
        self.elem4 = FakeWebElement(QRect(30, 180, 10, 10), self.frame)

    def test_not_scrolled(self):
        """Test base situation."""
        self.assertTrue(self.frame.geometry().contains(self.iframe.geometry()))
        self.assertTrue(webelem.is_visible(self.elem1, self.frame))
        self.assertTrue(webelem.is_visible(self.elem2, self.frame))
        self.assertFalse(webelem.is_visible(self.elem3, self.frame))
        self.assertTrue(webelem.is_visible(self.elem4, self.frame))

    def test_iframe_scrolled(self):
        """Scroll iframe down so elem3 gets visible and elem1/elem2 not."""
        self.iframe.scrollPosition.return_value = QPoint(0, 100)
        self.assertFalse(webelem.is_visible(self.elem1, self.frame))
        self.assertFalse(webelem.is_visible(self.elem2, self.frame))
        self.assertTrue(webelem.is_visible(self.elem3, self.frame))
        self.assertTrue(webelem.is_visible(self.elem4, self.frame))

    def test_mainframe_scrolled_iframe_visible(self):
        """Scroll mainframe down so iframe is partly visible but elem1 not."""
        self.frame.scrollPosition.return_value = QPoint(0, 50)
        geom = self.frame.geometry().translated(self.frame.scrollPosition())
        self.assertFalse(geom.contains(self.iframe.geometry()))
        self.assertTrue(geom.intersects(self.iframe.geometry()))
        self.assertFalse(webelem.is_visible(self.elem1, self.frame))
        self.assertTrue(webelem.is_visible(self.elem2, self.frame))
        self.assertFalse(webelem.is_visible(self.elem3, self.frame))
        self.assertTrue(webelem.is_visible(self.elem4, self.frame))

    def test_mainframe_scrolled_iframe_invisible(self):
        """Scroll mainframe down so iframe is invisible."""
        self.frame.scrollPosition.return_value = QPoint(0, 110)
        geom = self.frame.geometry().translated(self.frame.scrollPosition())
        self.assertFalse(geom.contains(self.iframe.geometry()))
        self.assertFalse(geom.intersects(self.iframe.geometry()))
        self.assertFalse(webelem.is_visible(self.elem1, self.frame))
        self.assertFalse(webelem.is_visible(self.elem2, self.frame))
        self.assertFalse(webelem.is_visible(self.elem3, self.frame))
        self.assertTrue(webelem.is_visible(self.elem4, self.frame))


class IsWritableTests(unittest.TestCase):

    """Check is_writable."""

    def test_writable(self):
        """Test a normal element."""
        elem = FakeWebElement()
        self.assertTrue(webelem.is_writable(elem))

    def test_disabled(self):
        """Test a disabled element."""
        elem = FakeWebElement(attributes=['disabled'])
        self.assertFalse(webelem.is_writable(elem))

    def test_readonly(self):
        """Test a readonly element."""
        elem = FakeWebElement(attributes=['readonly'])
        self.assertFalse(webelem.is_writable(elem))


class JavascriptEscapeTests(unittest.TestCase):

    """Check javascript_escape.

    Class attributes:
        STRINGS: A list of (input, output) tuples.
    """

    STRINGS = (
        ('foo\\bar', r'foo\\bar'),
        ('foo\nbar', r'foo\nbar'),
        ("foo'bar", r"foo\'bar"),
        ('foo"bar', r'foo\"bar'),
    )

    def test_fake_escape(self):
        """Test javascript escaping."""
        for before, after in self.STRINGS:
            self.assertEqual(webelem.javascript_escape(before), after)


class GetChildFramesTests(unittest.TestCase):

    """Check get_child_frames."""

    def test_single_frame(self):
        """Test get_child_frames with a single frame without children."""
        frame = FakeChildrenFrame()
        children = webelem.get_child_frames(frame)
        self.assertEqual(len(children), 1)
        self.assertIs(children[0], frame)
        frame.childFrames.assert_called_once_with()

    def test_one_level(self):
        r"""Test get_child_frames with this tree:

                  o   parent
                 / \
        child1  o   o  child2
        """
        child1 = FakeChildrenFrame()
        child2 = FakeChildrenFrame()
        parent = FakeChildrenFrame([child1, child2])
        children = webelem.get_child_frames(parent)
        self.assertEqual(len(children), 3)
        self.assertIs(children[0], parent)
        self.assertIs(children[1], child1)
        self.assertIs(children[2], child2)
        parent.childFrames.assert_called_once_with()
        child1.childFrames.assert_called_once_with()
        child2.childFrames.assert_called_once_with()

    def test_multiple_levels(self):
        r"""Test get_child_frames with this tree:

            o      root
           / \
          o   o    first
         /\   /\
        o  o o  o  second
        """
        second = [FakeChildrenFrame() for _ in range(4)]
        first = [FakeChildrenFrame(second[0:2]),
                 FakeChildrenFrame(second[2:4])]
        root = FakeChildrenFrame(first)
        children = webelem.get_child_frames(root)
        self.assertEqual(len(children), 7)
        self.assertIs(children[0], root)
        for frame in [root] + first + second:
            frame.childFrames.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
