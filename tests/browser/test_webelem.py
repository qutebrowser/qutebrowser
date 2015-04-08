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


def get_webelem(geometry=None, frame=None, null=False, visibility='',
                display='', attributes=None, tagname=None, classes=None):
    """Factory for WebElementWrapper objects based on a mock.

    Args:
        geometry: The geometry of the QWebElement as QRect.
        frame: The QWebFrame the element is in.
        null: Whether the element is null or not.
        visibility: The CSS visibility style property value.
        display: The CSS display style property value.
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

    def _style_property(name, strategy):
        """Helper function to act as styleProperty method."""
        if strategy != QWebElement.ComputedStyle:
            raise ValueError("styleProperty called with strategy != "
                             "ComputedStyle ({})!".format(strategy))
        if name == 'visibility':
            return visibility
        elif name == 'display':
            return display
        else:
            raise ValueError("styleProperty called with unknown name "
                             "'{}'".format(name))

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


class TestIsVisibleInvalid:

    """Tests for is_visible with invalid elements.

    Attributes:
        frame: The FakeWebFrame we're using to test.
    """

    @pytest.fixture(autouse=True)
    def setup(self, stubs):
        self.frame = stubs.FakeWebFrame(QRect(0, 0, 100, 100))

    def test_nullelem(self):
        """Passing an element with isNull() == True.

        geometry() and webFrame() should not be called, and ValueError should
        be raised.
        """
        elem = get_webelem()
        elem._elem.isNull.return_value = True
        with pytest.raises(webelem.IsNullError):
            elem.is_visible(self.frame)

    def test_invalid_invisible(self):
        """Test elements with an invalid geometry which are invisible."""
        elem = get_webelem(QRect(0, 0, 0, 0), self.frame)
        assert not elem.geometry().isValid()
        assert elem.geometry().x() == 0
        assert not elem.is_visible(self.frame)

    def test_invalid_visible(self):
        """Test elements with an invalid geometry which are visible.

        This seems to happen sometimes in the real world, with real elements
        which *are* visible, but don't have a valid geometry.
        """
        elem = get_webelem(QRect(10, 10, 0, 0), self.frame)
        assert not elem.geometry().isValid()
        assert elem.is_visible(self.frame)


class TestIsVisibleScroll:

    """Tests for is_visible when the frame is scrolled.

    Attributes:
        frame: The FakeWebFrame we're using to test.
    """

    @pytest.fixture(autouse=True)
    def setup(self, stubs):
        self.frame = stubs.FakeWebFrame(QRect(0, 0, 100, 100),
                                        scroll=QPoint(10, 10))

    def test_invisible(self):
        """Test elements which should be invisible due to scrolling."""
        elem = get_webelem(QRect(5, 5, 4, 4), self.frame)
        assert not elem.is_visible(self.frame)

    def test_visible(self):
        """Test elements which still should be visible after scrolling."""
        elem = get_webelem(QRect(10, 10, 1, 1), self.frame)
        assert elem.is_visible(self.frame)


class TestIsVisibleCss:

    """Tests for is_visible with CSS attributes.

    Attributes:
        frame: The FakeWebFrame we're using to test.
    """

    @pytest.fixture(autouse=True)
    def setup(self, stubs):
        self.frame = stubs.FakeWebFrame(QRect(0, 0, 100, 100))

    def test_visibility_visible(self):
        """Check that elements with "visibility = visible" are visible."""
        elem = get_webelem(QRect(0, 0, 10, 10), self.frame,
                           visibility='visible')
        assert elem.is_visible(self.frame)

    def test_visibility_hidden(self):
        """Check that elements with "visibility = hidden" are not visible."""
        elem = get_webelem(QRect(0, 0, 10, 10), self.frame,
                           visibility='hidden')
        assert not elem.is_visible(self.frame)

    def test_display_inline(self):
        """Check that elements with "display = inline" are visible."""
        elem = get_webelem(QRect(0, 0, 10, 10), self.frame, display='inline')
        assert elem.is_visible(self.frame)

    def test_display_none(self):
        """Check that elements with "display = none" are not visible."""
        elem = get_webelem(QRect(0, 0, 10, 10), self.frame, display='none')
        assert not elem.is_visible(self.frame)


class TestIsVisibleIframe:

    """Tests for is_visible with a child frame.

    Attributes:
        frame: The FakeWebFrame we're using to test.
        iframe: The iframe inside frame.
        elem1-elem4: FakeWebElements to test.
    """

    @pytest.fixture(autouse=True)
    def setup(self, stubs):
        """Set up the following base situation.

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
        self.frame = stubs.FakeWebFrame(QRect(0, 0, 300, 300))
        self.iframe = stubs.FakeWebFrame(QRect(0, 10, 100, 100),
                                         parent=self.frame)
        self.elem1 = get_webelem(QRect(0, 0, 10, 10), self.iframe)
        self.elem2 = get_webelem(QRect(20, 90, 10, 10), self.iframe)
        self.elem3 = get_webelem(QRect(20, 150, 10, 10), self.iframe)
        self.elem4 = get_webelem(QRect(30, 180, 10, 10), self.frame)

    def test_not_scrolled(self):
        """Test base situation."""
        assert self.frame.geometry().contains(self.iframe.geometry())
        assert self.elem1.is_visible(self.frame)
        assert self.elem2.is_visible(self.frame)
        assert not self.elem3.is_visible(self.frame)
        assert self.elem4.is_visible(self.frame)

    def test_iframe_scrolled(self):
        """Scroll iframe down so elem3 gets visible and elem1/elem2 not."""
        self.iframe.scrollPosition.return_value = QPoint(0, 100)
        assert not self.elem1.is_visible(self.frame)
        assert not self.elem2.is_visible(self.frame)
        assert self.elem3.is_visible(self.frame)
        assert self.elem4.is_visible(self.frame)

    def test_mainframe_scrolled_iframe_visible(self):
        """Scroll mainframe down so iframe is partly visible but elem1 not."""
        self.frame.scrollPosition.return_value = QPoint(0, 50)
        geom = self.frame.geometry().translated(self.frame.scrollPosition())
        assert not geom.contains(self.iframe.geometry())
        assert geom.intersects(self.iframe.geometry())
        assert not self.elem1.is_visible(self.frame)
        assert self.elem2.is_visible(self.frame)
        assert not self.elem3.is_visible(self.frame)
        assert self.elem4.is_visible(self.frame)

    def test_mainframe_scrolled_iframe_invisible(self):
        """Scroll mainframe down so iframe is invisible."""
        self.frame.scrollPosition.return_value = QPoint(0, 110)
        geom = self.frame.geometry().translated(self.frame.scrollPosition())
        assert not geom.contains(self.iframe.geometry())
        assert not geom.intersects(self.iframe.geometry())
        assert not self.elem1.is_visible(self.frame)
        assert not self.elem2.is_visible(self.frame)
        assert not self.elem3.is_visible(self.frame)
        assert self.elem4.is_visible(self.frame)


class TestIsWritable:

    """Check is_writable."""

    def test_writable(self):
        """Test a normal element."""
        elem = get_webelem()
        assert elem.is_writable()

    def test_disabled(self):
        """Test a disabled element."""
        elem = get_webelem(attributes=['disabled'])
        assert not elem.is_writable()

    def test_readonly(self):
        """Test a readonly element."""
        elem = get_webelem(attributes=['readonly'])
        assert not elem.is_writable()


class TestJavascriptEscape:

    """Check javascript_escape.

    Class attributes:
        STRINGS: A list of (input, output) tuples.
    """

    @pytest.mark.parametrize('before, after', [
        ('foo\\bar', r'foo\\bar'),
        ('foo\nbar', r'foo\nbar'),
        ("foo'bar", r"foo\'bar"),
        ('foo"bar', r'foo\"bar'),
    ])
    def test_fake_escape(self, before, after):
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

    @pytest.yield_fixture(autouse=True)
    def setup(self):
        old_config = webelem.config
        webelem.config = None
        yield
        webelem.config = old_config

    @pytest.fixture
    def stub_config(self, stubs, mocker):
        """Fixture to create a config stub with an input section."""
        config = stubs.ConfigStub({'input': {}})
        mocker.patch('qutebrowser.browser.webelem.config', new=config)
        return config

    def test_input_plain(self):
        """Test with plain input element."""
        elem = get_webelem(tagname='input')
        assert elem.is_editable()

    def test_input_text(self):
        """Test with text input element."""
        elem = get_webelem(tagname='input', attributes={'type': 'text'})
        assert elem.is_editable()

    def test_input_text_caps(self):
        """Test with text input element with caps attributes."""
        elem = get_webelem(tagname='INPUT', attributes={'TYPE': 'TEXT'})
        assert elem.is_editable()

    def test_input_email(self):
        """Test with email input element."""
        elem = get_webelem(tagname='input', attributes={'type': 'email'})
        assert elem.is_editable()

    def test_input_url(self):
        """Test with url input element."""
        elem = get_webelem(tagname='input', attributes={'type': 'url'})
        assert elem.is_editable()

    def test_input_tel(self):
        """Test with tel input element."""
        elem = get_webelem(tagname='input', attributes={'type': 'tel'})
        assert elem.is_editable()

    def test_input_number(self):
        """Test with number input element."""
        elem = get_webelem(tagname='input', attributes={'type': 'number'})
        assert elem.is_editable()

    def test_input_password(self):
        """Test with password input element."""
        elem = get_webelem(tagname='input', attributes={'type': 'password'})
        assert elem.is_editable()

    def test_input_search(self):
        """Test with search input element."""
        elem = get_webelem(tagname='input', attributes={'type': 'search'})
        assert elem.is_editable()

    def test_input_button(self):
        """Button should not be editable."""
        elem = get_webelem(tagname='input', attributes={'type': 'button'})
        assert not elem.is_editable()

    def test_input_checkbox(self):
        """Checkbox should not be editable."""
        elem = get_webelem(tagname='input', attributes={'type': 'checkbox'})
        assert not elem.is_editable()

    def test_textarea(self):
        """Test textarea element."""
        elem = get_webelem(tagname='textarea')
        assert elem.is_editable()

    def test_select(self):
        """Test selectbox."""
        elem = get_webelem(tagname='select')
        assert not elem.is_editable()

    def test_input_disabled(self):
        """Test disabled input element."""
        elem = get_webelem(tagname='input', attributes={'disabled': None})
        assert not elem.is_editable()

    def test_input_readonly(self):
        """Test readonly input element."""
        elem = get_webelem(tagname='input', attributes={'readonly': None})
        assert not elem.is_editable()

    def test_textarea_disabled(self):
        """Test disabled textarea element."""
        elem = get_webelem(tagname='textarea', attributes={'disabled': None})
        assert not elem.is_editable()

    def test_textarea_readonly(self):
        """Test readonly textarea element."""
        elem = get_webelem(tagname='textarea', attributes={'readonly': None})
        assert not elem.is_editable()

    def test_embed_true(self, stub_config):
        """Test embed-element with insert-mode-on-plugins true."""
        stub_config.data['input']['insert-mode-on-plugins'] = True
        elem = get_webelem(tagname='embed')
        assert elem.is_editable()

    def test_applet_true(self, stub_config):
        """Test applet-element with insert-mode-on-plugins true."""
        stub_config.data['input']['insert-mode-on-plugins'] = True
        elem = get_webelem(tagname='applet')
        assert elem.is_editable()

    def test_embed_false(self, stub_config):
        """Test embed-element with insert-mode-on-plugins false."""
        stub_config.data['input']['insert-mode-on-plugins'] = False
        elem = get_webelem(tagname='embed')
        assert not elem.is_editable()

    def test_applet_false(self, stub_config):
        """Test applet-element with insert-mode-on-plugins false."""
        stub_config.data['input']['insert-mode-on-plugins'] = False
        elem = get_webelem(tagname='applet')
        assert not elem.is_editable()

    def test_object_no_type(self):
        """Test object-element without type."""
        elem = get_webelem(tagname='object')
        assert not elem.is_editable()

    def test_object_image(self):
        """Test object-element with image type."""
        elem = get_webelem(tagname='object', attributes={'type': 'image/gif'})
        assert not elem.is_editable()

    def test_object_application(self, stub_config):
        """Test object-element with application type."""
        stub_config.data['input']['insert-mode-on-plugins'] = True
        elem = get_webelem(tagname='object',
                           attributes={'type': 'application/foo'})
        assert elem.is_editable()

    def test_object_application_false(self, stub_config):
        """Test object-element with application type but not ...-on-plugins."""
        stub_config.data['input']['insert-mode-on-plugins'] = False
        elem = get_webelem(tagname='object',
                           attributes={'type': 'application/foo'})
        assert not elem.is_editable()

    def test_object_classid(self, stub_config):
        """Test object-element with classid."""
        stub_config.data['input']['insert-mode-on-plugins'] = True
        elem = get_webelem(tagname='object',
                           attributes={'type': 'foo', 'classid': 'foo'})
        assert elem.is_editable()

    def test_object_classid_false(self, stub_config):
        """Test object-element with classid but not insert-mode-on-plugins."""
        stub_config.data['input']['insert-mode-on-plugins'] = False
        elem = get_webelem(tagname='object',
                           attributes={'type': 'foo', 'classid': 'foo'})
        assert not elem.is_editable()

    def test_div_empty(self):
        """Test div-element without class."""
        elem = get_webelem(tagname='div')
        assert not elem.is_editable()

    def test_div_noneditable(self):
        """Test div-element with non-editable class."""
        elem = get_webelem(tagname='div', classes='foo-kix-bar')
        assert not elem.is_editable()

    def test_div_xik(self):
        """Test div-element with xik class."""
        elem = get_webelem(tagname='div', classes='foo kix-foo')
        assert elem.is_editable()

    def test_div_xik_caps(self):
        """Test div-element with xik class in caps.

        This tests if classes are case sensitive as they should.
        """
        elem = get_webelem(tagname='div', classes='KIX-FOO')
        assert not elem.is_editable()

    def test_div_codemirror(self):
        """Test div-element with codemirror class."""
        elem = get_webelem(tagname='div', classes='foo CodeMirror-foo')
        assert elem.is_editable()
