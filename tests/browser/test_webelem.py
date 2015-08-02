# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# pylint: disable=protected-access

"""Tests for the webelement utils."""

from unittest import mock
import collections.abc

from PyQt5.QtCore import QRect, QPoint
from PyQt5.QtWebKit import QWebElement
import pytest

from qutebrowser.browser import webelem


def get_webelem(geometry=None, frame=None, null=False, style=None,
                display='', attributes=None, tagname=None, classes=None):
    """Factory for WebElementWrapper objects based on a mock.

    Args:
        geometry: The geometry of the QWebElement as QRect.
        frame: The QWebFrame the element is in.
        null: Whether the element is null or not.
        style: A dict with the styleAttributes of the element.
        attributes: Boolean HTML attributes to be added.
        tagname: The tag name.
        classes: HTML classes to be added.
    """
    elem = mock.Mock()
    elem.isNull.return_value = null
    elem.geometry.return_value = geometry
    elem.webFrame.return_value = frame
    elem.tagName.return_value = tagname
    elem.toOuterXml.return_value = '<fakeelem/>'

    if attributes is not None:
        if not isinstance(attributes, collections.abc.Mapping):
            attributes = {e: None for e in attributes}
        elem.hasAttribute.side_effect = lambda k: k in attributes
        elem.attribute.side_effect = lambda k: attributes.get(k, '')
        elem.attributeNames.return_value = list(attributes)
    else:
        elem.hasAttribute.return_value = False
        elem.attribute.return_value = ''
        elem.attributeNames.return_value = []

    if classes is not None:
        elem.classes.return_value = classes.split(' ')
    else:
        elem.classes.return_value = []

    style_dict = {'visibility': '', 'display': ''}
    if style is not None:
        style_dict.update(style)

    def _style_property(name, strategy):
        """Helper function to act as styleProperty method."""
        if strategy != QWebElement.ComputedStyle:
            raise ValueError("styleProperty called with strategy != "
                             "ComputedStyle ({})!".format(strategy))
        return style_dict[name]

    elem.styleProperty.side_effect = _style_property
    wrapped = webelem.WebElementWrapper(elem)
    if attributes is not None:
        wrapped.update(attributes)
    return wrapped


class TestWebElementWrapper:

    """Test WebElementWrapper."""

    def test_nullelem(self):
        """Test __init__ with a null element."""
        with pytest.raises(webelem.IsNullError):
            get_webelem(null=True)


class TestIsVisible:

    @pytest.fixture
    def frame(self, stubs):
        return stubs.FakeWebFrame(QRect(0, 0, 100, 100))

    def test_nullelem(self, frame):
        """Passing an element with isNull() == True.

        geometry() and webFrame() should not be called, and ValueError should
        be raised.
        """
        elem = get_webelem()
        elem._elem.isNull.return_value = True
        with pytest.raises(webelem.IsNullError):
            elem.is_visible(frame)

    def test_invalid_invisible(self, frame):
        """Test elements with an invalid geometry which are invisible."""
        elem = get_webelem(QRect(0, 0, 0, 0), frame)
        assert not elem.geometry().isValid()
        assert elem.geometry().x() == 0
        assert not elem.is_visible(frame)

    def test_invalid_visible(self, frame):
        """Test elements with an invalid geometry which are visible.

        This seems to happen sometimes in the real world, with real elements
        which *are* visible, but don't have a valid geometry.
        """
        elem = get_webelem(QRect(10, 10, 0, 0), frame)
        assert not elem.geometry().isValid()
        assert elem.is_visible(frame)

    @pytest.mark.parametrize('geometry, visible', [
        (QRect(5, 5, 4, 4), False),
        (QRect(10, 10, 1, 1), True),
    ])
    def test_scrolled(self, geometry, visible, stubs):
        scrolled_frame = stubs.FakeWebFrame(QRect(0, 0, 100, 100),
                                            scroll=QPoint(10, 10))
        elem = get_webelem(geometry, scrolled_frame)
        assert elem.is_visible(scrolled_frame) == visible

    @pytest.mark.parametrize('style, visible', [
        ({'visibility': 'visible'}, True),
        ({'visibility': 'hidden'}, False),
        ({'display': 'inline'}, True),
        ({'display': 'none'}, False),
        ({'visibility': 'visible', 'display': 'none'}, False),
        ({'visibility': 'hidden', 'display': 'inline'}, False),
    ])
    def test_css_attributes(self, frame, style, visible):
        elem = get_webelem(QRect(0, 0, 10, 10), frame, style=style)
        assert elem.is_visible(frame) == visible


class TestIsVisibleIframe:

    """Tests for is_visible with a child frame.

    Attributes:
        frame: The FakeWebFrame we're using to test.
        iframe: The iframe inside frame.
        elem1-elem4: FakeWebElements to test.
    """

    Objects = collections.namedtuple('Objects', ['frame', 'iframe', 'elems'])

    @pytest.fixture
    def objects(self, stubs):
        """Set up the following base situation.

             0, 0                         300, 0
              ##############################
              #                            #
         0,10 # iframe  100,10             #
              #**********                  #
              #*e       * elems[0]: 0, 0 in iframe (visible)
              #*        *                  #
              #* e      * elems[1]: 20,90 in iframe (visible)
              #**********                  #
        0,110 #.        .100,110           #
              #.        .                  #
              #. e      . elems[2]: 20,150 in iframe (not visible)
              #..........                  #
              #     e     elems[3]: 30, 180 in main frame (visible)
              #                            #
              #          frame             #
              ##############################
            300, 0                         300, 300

        Returns an Objects namedtuple with frame/iframe/elems attributes.
        """
        frame = stubs.FakeWebFrame(QRect(0, 0, 300, 300))
        iframe = stubs.FakeWebFrame(QRect(0, 10, 100, 100), parent=frame)
        assert frame.geometry().contains(iframe.geometry())
        elems = [
            get_webelem(QRect(0, 0, 10, 10), iframe),
            get_webelem(QRect(20, 90, 10, 10), iframe),
            get_webelem(QRect(20, 150, 10, 10), iframe),
            get_webelem(QRect(30, 180, 10, 10), frame),
        ]

        assert elems[0].is_visible(frame)
        assert elems[1].is_visible(frame)
        assert not elems[2].is_visible(frame)
        assert elems[3].is_visible(frame)

        return self.Objects(frame=frame, iframe=iframe, elems=elems)

    def test_iframe_scrolled(self, objects):
        """Scroll iframe down so elem3 gets visible and elem1/elem2 not."""
        objects.iframe.scrollPosition.return_value = QPoint(0, 100)
        assert not objects.elems[0].is_visible(objects.frame)
        assert not objects.elems[1].is_visible(objects.frame)
        assert objects.elems[2].is_visible(objects.frame)
        assert objects.elems[3].is_visible(objects.frame)

    def test_mainframe_scrolled_iframe_visible(self, objects):
        """Scroll mainframe down so iframe is partly visible but elem1 not."""
        objects.frame.scrollPosition.return_value = QPoint(0, 50)
        geom = objects.frame.geometry().translated(
            objects.frame.scrollPosition())
        assert not geom.contains(objects.iframe.geometry())
        assert geom.intersects(objects.iframe.geometry())
        assert not objects.elems[0].is_visible(objects.frame)
        assert objects.elems[1].is_visible(objects.frame)
        assert not objects.elems[2].is_visible(objects.frame)
        assert objects.elems[3].is_visible(objects.frame)

    def test_mainframe_scrolled_iframe_invisible(self, objects):
        """Scroll mainframe down so iframe is invisible."""
        objects.frame.scrollPosition.return_value = QPoint(0, 110)
        geom = objects.frame.geometry().translated(
            objects.frame.scrollPosition())
        assert not geom.contains(objects.iframe.geometry())
        assert not geom.intersects(objects.iframe.geometry())
        assert not objects.elems[0].is_visible(objects.frame)
        assert not objects.elems[1].is_visible(objects.frame)
        assert not objects.elems[2].is_visible(objects.frame)
        assert objects.elems[3].is_visible(objects.frame)


@pytest.mark.parametrize('attributes, writable', [
    ([], True),
    (['disabled'], False),
    (['readonly'], False),
    (['disabled', 'readonly'], False),
])
def test_is_writable(attributes, writable):
    elem = get_webelem(attributes=attributes)
    assert elem.is_writable() == writable


@pytest.mark.parametrize('before, after', [
    ('foo\\bar', r'foo\\bar'),
    ('foo\nbar', r'foo\nbar'),
    ("foo'bar", r"foo\'bar"),
    ('foo"bar', r'foo\"bar'),
])
def test_fake_escape(before, after):
    """Test javascript escaping."""
    assert webelem.javascript_escape(before) == after


class TestGetChildFrames:

    """Check get_child_frames."""

    def test_single_frame(self, stubs):
        """Test get_child_frames with a single frame without children."""
        frame = stubs.FakeChildrenFrame()
        children = webelem.get_child_frames(frame)
        assert len(children) == 1
        assert children[0] is frame
        frame.childFrames.assert_called_once_with()

    def test_one_level(self, stubs):
        r"""Test get_child_frames with one level of children.

                  o   parent
                 / \
        child1  o   o  child2
        """
        child1 = stubs.FakeChildrenFrame()
        child2 = stubs.FakeChildrenFrame()
        parent = stubs.FakeChildrenFrame([child1, child2])
        children = webelem.get_child_frames(parent)
        assert len(children) == 3
        assert children[0] is parent
        assert children[1] is child1
        assert children[2] is child2
        parent.childFrames.assert_called_once_with()
        child1.childFrames.assert_called_once_with()
        child2.childFrames.assert_called_once_with()

    def test_multiple_levels(self, stubs):
        r"""Test get_child_frames with multiple levels of children.

            o      root
           / \
          o   o    first
         /\   /\
        o  o o  o  second
        """
        second = [stubs.FakeChildrenFrame() for _ in range(4)]
        first = [stubs.FakeChildrenFrame(second[0:2]),
                 stubs.FakeChildrenFrame(second[2:4])]
        root = stubs.FakeChildrenFrame(first)
        children = webelem.get_child_frames(root)
        assert len(children) == 7
        assert children[0] is root
        for frame in [root] + first + second:
            frame.childFrames.assert_called_once_with()


class TestIsEditable:

    """Tests for is_editable."""

    @pytest.fixture
    def stubbed_config(self, config_stub, monkeypatch):
        """Fixture to create a config stub with an input section."""
        config_stub.data = {'input': {}}
        monkeypatch.setattr('qutebrowser.browser.webelem.config', config_stub)
        return config_stub

    @pytest.mark.parametrize('tagname, attributes, editable', [
        ('input', {}, True),
        ('input', {'type': 'text'}, True),
        ('INPUT', {'TYPE': 'TEXT'}, True),  # caps attributes/name
        ('input', {'type': 'email'}, True),
        ('input', {'type': 'url'}, True),
        ('input', {'type': 'tel'}, True),
        ('input', {'type': 'number'}, True),
        ('input', {'type': 'password'}, True),
        ('input', {'type': 'search'}, True),
        ('textarea', {}, True),

        ('input', {'type': 'button'}, False),
        ('input', {'type': 'checkbox'}, False),
        ('select', {}, False),

        ('input', {'disabled': None}, False),
        ('input', {'readonly': None}, False),
        ('textarea', {'disabled': None}, False),
        ('textarea', {'readonly': None}, False),
        ('object', {}, False),
        ('object', {'type': 'image/gif'}, False),
    ])
    def test_is_editable(self, tagname, attributes, editable):
        elem = get_webelem(tagname=tagname, attributes=attributes)
        assert elem.is_editable() == editable

    @pytest.mark.parametrize('classes, editable', [
        (None, False),
        ('foo-kix-bar', False),
        ('foo kix-foo', True),
        ('KIX-FOO', False),
        ('foo CodeMirror-foo', True),
    ])
    def test_is_editable_div(self, tagname, classes, editable):
        elem = get_webelem(tagname='div', classes=classes)
        assert elem.is_editable() == editable

    @pytest.mark.parametrize('setting, tagname, attributes, editable', [
        (True, 'embed', {}, True),
        (True, 'embed', {}, True),
        (False, 'applet', {}, False),
        (False, 'applet', {}, False),
        (True, 'object', {'type': 'application/foo'}, True),
        (False, 'object', {'type': 'application/foo'}, False),
        (True, 'object', {'type': 'foo', 'classid': 'foo'}, True),
        (False, 'object', {'type': 'foo', 'classid': 'foo'}, False),
    ])
    def test_is_editable_div(self, stubbed_config, setting, tagname,
                             attributes, editable):
        stubbed_config.data['input']['insert-mode-on-plugins'] = setting
        elem = get_webelem(tagname=tagname, attributes=attributes)
        assert elem.is_editable() == editable
