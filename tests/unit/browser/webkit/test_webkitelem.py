# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from unittest import mock
import collections.abc
import operator
import itertools

from PyQt5.QtCore import QRect, QPoint, QUrl
from PyQt5.QtWebKit import QWebElement
import pytest

from qutebrowser.browser import webelem
from qutebrowser.browser.webkit import webkitelem


def get_webelem(geometry=None, frame=None, *, null=False, style=None,
                attributes=None, tagname=None, classes=None,
                parent=None, js_rect_return=None, zoom_text_only=False):
    """Factory for WebKitElement objects based on a mock.

    Args:
        geometry: The geometry of the QWebElement as QRect.
        frame: The QWebFrame the element is in.
        null: Whether the element is null or not.
        style: A dict with the styleAttributes of the element.
        attributes: Boolean HTML attributes to be added.
        tagname: The tag name.
        classes: HTML classes to be added.
        js_rect_return: If None, what evaluateJavaScript returns is based on
                        geometry. If set, the return value of
                        evaluateJavaScript.
        zoom_text_only: Whether zoom-text-only is set in the config
    """
    # pylint: disable=too-many-locals,too-many-branches
    elem = mock.Mock()
    elem.isNull.return_value = null
    elem.geometry.return_value = geometry
    elem.webFrame.return_value = frame
    elem.tagName.return_value = tagname
    elem.toOuterXml.return_value = '<fakeelem/>'
    elem.toPlainText.return_value = 'text'
    elem.parent.return_value = parent

    if geometry is not None:
        if frame is None:
            scroll_x = 0
            scroll_y = 0
        else:
            scroll_x = frame.scrollPosition().x()
            scroll_y = frame.scrollPosition().y()

        if js_rect_return is None:
            if frame is None or zoom_text_only:
                zoom = 1.0
            else:
                zoom = frame.zoomFactor()

            elem.evaluateJavaScript.return_value = {
                "length": 1,
                "0": {
                    "left": (geometry.left() - scroll_x) / zoom,
                    "top": (geometry.top() - scroll_y) / zoom,
                    "right": (geometry.right() - scroll_x) / zoom,
                    "bottom": (geometry.bottom() - scroll_y) / zoom,
                    "width": geometry.width() / zoom,
                    "height": geometry.height() / zoom,
                }
            }
        else:
            elem.evaluateJavaScript.return_value = js_rect_return

    attribute_dict = {}
    if attributes is None:
        pass
    elif not isinstance(attributes, collections.abc.Mapping):
        attribute_dict.update({e: None for e in attributes})
    else:
        attribute_dict.update(attributes)

    elem.hasAttribute.side_effect = lambda k: k in attribute_dict
    elem.attribute.side_effect = lambda k: attribute_dict.get(k, '')
    elem.setAttribute.side_effect = (lambda k, v:
                                     operator.setitem(attribute_dict, k, v))
    elem.removeAttribute.side_effect = attribute_dict.pop
    elem.attributeNames.return_value = list(attribute_dict)

    if classes is not None:
        elem.classes.return_value = classes.split(' ')
    else:
        elem.classes.return_value = []

    style_dict = {'visibility': '', 'display': '', 'foo': 'bar'}
    if style is not None:
        style_dict.update(style)

    def _style_property(name, strategy):
        """Helper function to act as styleProperty method."""
        if strategy != QWebElement.ComputedStyle:
            raise ValueError("styleProperty called with strategy != "
                             "ComputedStyle ({})!".format(strategy))
        return style_dict[name]

    elem.styleProperty.side_effect = _style_property
    wrapped = webkitelem.WebKitElement(elem)
    return wrapped


class SelectionAndFilterTests:

    """Generator for tests for TestSelectionsAndFilters."""

    # A mapping of an HTML element to a list of groups where the selectors
    # (after filtering) should match.
    #
    # Based on this, test cases are generated to make sure it matches those
    # groups and not the others.

    TESTS = [
        ('<foo />', []),
        ('<foo bar="baz"/>', []),
        ('<foo href="baz"/>', [webelem.Group.url]),
        ('<foo src="baz"/>', [webelem.Group.url]),

        ('<a />', [webelem.Group.all]),
        ('<a href="foo" />', [webelem.Group.all, webelem.Group.links,
                              webelem.Group.prevnext, webelem.Group.url]),
        ('<a href="javascript://foo" />', [webelem.Group.all,
                                           webelem.Group.url]),

        ('<area />', [webelem.Group.all]),
        ('<area href="foo" />', [webelem.Group.all, webelem.Group.links,
                                 webelem.Group.prevnext, webelem.Group.url]),
        ('<area href="javascript://foo" />', [webelem.Group.all,
                                              webelem.Group.url]),

        ('<link />', [webelem.Group.all]),
        ('<link href="foo" />', [webelem.Group.all, webelem.Group.links,
                                 webelem.Group.prevnext, webelem.Group.url]),
        ('<link href="javascript://foo" />', [webelem.Group.all,
                                              webelem.Group.url]),

        ('<textarea />', [webelem.Group.all, webelem.Group.inputs]),
        ('<select />', [webelem.Group.all]),

        ('<input />', [webelem.Group.all, webelem.Group.inputs]),
        ('<input type="hidden" />', []),
        ('<input type="text" />', [webelem.Group.inputs, webelem.Group.all]),
        ('<input type="email" />', [webelem.Group.inputs, webelem.Group.all]),
        ('<input type="url" />', [webelem.Group.inputs, webelem.Group.all]),
        ('<input type="tel" />', [webelem.Group.inputs, webelem.Group.all]),
        ('<input type="number" />', [webelem.Group.inputs, webelem.Group.all]),
        ('<input type="password" />', [webelem.Group.inputs,
                                       webelem.Group.all]),
        ('<input type="search" />', [webelem.Group.inputs, webelem.Group.all]),

        ('<button />', [webelem.Group.all]),
        ('<button href="foo" />', [webelem.Group.all, webelem.Group.prevnext,
                                   webelem.Group.url]),
        ('<button href="javascript://foo" />', [webelem.Group.all,
                                                webelem.Group.url]),

        # We can't easily test <frame>/<iframe> as they vanish when setting
        # them via QWebFrame::setHtml...

        ('<p onclick="foo" foo="bar"/>', [webelem.Group.all]),
        ('<p onmousedown="foo" foo="bar"/>', [webelem.Group.all]),
        ('<p role="option" foo="bar"/>', [webelem.Group.all]),
        ('<p role="button" foo="bar"/>', [webelem.Group.all]),
        ('<p role="button" href="bar"/>', [webelem.Group.all,
                                           webelem.Group.prevnext,
                                           webelem.Group.url]),
    ]

    GROUPS = list(webelem.Group)

    COMBINATIONS = list(itertools.product(TESTS, GROUPS))

    def __init__(self):
        self.tests = list(self._generate_tests())

    def _generate_tests(self):
        for (val, matching_groups), group in self.COMBINATIONS:
            if group in matching_groups:
                yield group, val, True
            else:
                yield group, val, False


class TestSelectorsAndFilters:

    TESTS = SelectionAndFilterTests().tests

    def test_test_generator(self):
        assert self.TESTS

    @pytest.mark.parametrize('group, val, matching', TESTS)
    def test_selectors(self, webframe, group, val, matching):
        webframe.setHtml('<html><body>{}</body></html>'.format(val))
        # Make sure setting HTML succeeded and there's a new element
        assert len(webframe.findAllElements('*')) == 3
        elems = webframe.findAllElements(webelem.SELECTORS[group])
        elems = [webkitelem.WebKitElement(e) for e in elems]
        filterfunc = webelem.FILTERS.get(group, lambda e: True)
        elems = [e for e in elems if filterfunc(e)]
        assert bool(elems) == matching


class TestWebKitElement:

    """Generic tests for WebKitElement.

    Note: For some methods, there's a dedicated test class with more involved
    tests.
    """

    @pytest.fixture
    def elem(self):
        return get_webelem()

    def test_nullelem(self):
        """Test __init__ with a null element."""
        with pytest.raises(webkitelem.IsNullError):
            get_webelem(null=True)

    def test_double_wrap(self, elem):
        """Test wrapping a WebKitElement."""
        with pytest.raises(TypeError) as excinfo:
            webkitelem.WebKitElement(elem)
        assert str(excinfo.value) == "Trying to wrap a wrapper!"

    @pytest.mark.parametrize('code', [
        str,
        lambda e: e[None],
        lambda e: operator.setitem(e, None, None),
        lambda e: operator.delitem(e, None),
        lambda e: None in e,
        list,  # __iter__
        len,
        lambda e: e.frame(),
        lambda e: e.geometry(),
        lambda e: e.style_property('visibility', strategy='computed'),
        lambda e: e.text(),
        lambda e: e.set_text('foo'),
        lambda e: e.is_writable(),
        lambda e: e.is_content_editable(),
        lambda e: e.is_editable(),
        lambda e: e.is_text_input(),
        lambda e: e.remove_blank_target(),
        lambda e: e.debug_text(),
        lambda e: e.outer_xml(),
        lambda e: e.tag_name(),
        lambda e: e.run_js_async(''),
        lambda e: e.rect_on_view(callback=None),
        lambda e: e.is_visible(None),
    ], ids=['str', 'getitem', 'setitem', 'delitem', 'contains', 'iter', 'len',
            'frame', 'geometry', 'style_property', 'text', 'set_text',
            'is_writable', 'is_content_editable', 'is_editable',
            'is_text_input', 'remove_blank_target', 'debug_text', 'outer_xml',
            'tag_name', 'run_js_async', 'rect_on_view', 'is_visible'])
    def test_vanished(self, elem, code):
        """Make sure methods check if the element is vanished."""
        elem._elem.isNull.return_value = True
        elem._elem.tagName.return_value = 'span'
        with pytest.raises(webkitelem.IsNullError):
            code(elem)

    def test_str(self, elem):
        assert str(elem) == 'text'

    @pytest.mark.parametrize('is_null, expected', [
        (False, "<qutebrowser.browser.webkit.webkitelem.WebKitElement "
                "html='<fakeelem/>'>"),
        (True, '<qutebrowser.browser.webkit.webkitelem.WebKitElement '
               'html=None>'),
    ])
    def test_repr(self, elem, is_null, expected):
        elem._elem.isNull.return_value = is_null
        assert repr(elem) == expected

    def test_getitem(self):
        elem = get_webelem(attributes={'foo': 'bar'})
        assert elem['foo'] == 'bar'

    def test_getitem_keyerror(self, elem):
        with pytest.raises(KeyError):
            elem['foo']  # pylint: disable=pointless-statement

    def test_setitem(self, elem):
        elem['foo'] = 'bar'
        assert elem._elem.attribute('foo') == 'bar'

    def test_delitem(self):
        elem = get_webelem(attributes={'foo': 'bar'})
        del elem['foo']
        assert not elem._elem.hasAttribute('foo')

    def test_setitem_keyerror(self, elem):
        with pytest.raises(KeyError):
            del elem['foo']

    def test_contains(self):
        elem = get_webelem(attributes={'foo': 'bar'})
        assert 'foo' in elem
        assert 'bar' not in elem

    def test_not_eq(self):
        one = get_webelem()
        two = get_webelem()
        assert one != two

    def test_eq(self):
        one = get_webelem()
        two = webkitelem.WebKitElement(one._elem)
        assert one == two

    def test_eq_other_type(self):
        assert get_webelem() != object()

    @pytest.mark.parametrize('attributes, expected', [
        ({'one': '1', 'two': '2'}, {'one', 'two'}),
        ({}, set()),
    ])
    def test_iter(self, attributes, expected):
        elem = get_webelem(attributes=attributes)
        assert set(elem) == expected

    @pytest.mark.parametrize('attributes, length', [
        ({'one': '1', 'two': '2'}, 2),
        ({}, 0),
    ])
    def test_len(self, attributes, length):
        elem = get_webelem(attributes=attributes)
        assert len(elem) == length

    @pytest.mark.parametrize('attributes, writable', [
        ([], True),
        (['disabled'], False),
        (['readonly'], False),
        (['disabled', 'readonly'], False),
    ])
    def test_is_writable(self, attributes, writable):
        elem = get_webelem(attributes=attributes)
        assert elem.is_writable() == writable

    @pytest.mark.parametrize('attributes, expected', [
        ({}, False),
        ({'contenteditable': 'false'}, False),
        ({'contenteditable': 'inherit'}, False),
        ({'contenteditable': 'true'}, True),
    ])
    def test_is_content_editable(self, attributes, expected):
        elem = get_webelem(attributes=attributes)
        assert elem.is_content_editable() == expected

    @pytest.mark.parametrize('tagname, attributes, expected', [
        ('input', {}, True),
        ('textarea', {}, True),
        ('select', {}, False),
        ('foo', {'role': 'combobox'}, True),
        ('foo', {'role': 'textbox'}, True),
        ('foo', {'role': 'bar'}, False),
        ('input', {'role': 'bar'}, True),
    ])
    def test_is_text_input(self, tagname, attributes, expected):
        elem = get_webelem(tagname=tagname, attributes=attributes)
        assert elem.is_text_input() == expected

    @pytest.mark.parametrize('xml, expected', [
        ('<fakeelem/>', '<fakeelem/>'),
        ('<foo>\n<bar/>\n</foo>', '<foo><bar/></foo>'),
        ('<foo>{}</foo>'.format('x' * 500), '<foo>{}…'.format('x' * 494)),
    ], ids=['fakeelem', 'newlines', 'long'])
    def test_debug_text(self, elem, xml, expected):
        elem._elem.toOuterXml.return_value = xml
        assert elem.debug_text() == expected

    @pytest.mark.parametrize('attribute, code', [
        ('webFrame', lambda e: e.frame()),
        ('geometry', lambda e: e.geometry()),
        ('toOuterXml', lambda e: e.outer_xml()),
    ])
    def test_simple_getters(self, elem, attribute, code):
        sentinel = object()
        mock = getattr(elem._elem, attribute)
        setattr(mock, 'return_value', sentinel)
        assert code(elem) is sentinel

    def test_tag_name(self, elem):
        elem._elem.tagName.return_value = 'SPAN'
        assert elem.tag_name() == 'span'

    def test_style_property(self, elem):
        assert elem.style_property('foo', strategy='computed') == 'bar'

    @pytest.mark.parametrize('use_js, editable, expected', [
        (True, 'false', 'js'),
        (True, 'true', 'nojs'),
        (False, 'false', 'nojs'),
        (False, 'true', 'nojs'),
    ])
    def test_text(self, use_js, editable, expected):
        elem = get_webelem(attributes={'contenteditable': editable})
        elem._elem.toPlainText.return_value = 'nojs'
        elem._elem.evaluateJavaScript.return_value = 'js'
        assert elem.text(use_js=use_js) == expected

    @pytest.mark.parametrize('use_js, editable, text, uses_js, arg', [
        (True, 'false', 'foo', True, "this.value='foo'"),
        (True, 'false', "foo'bar", True, r"this.value='foo\'bar'"),
        (True, 'true', 'foo', False, 'foo'),
        (False, 'false', 'foo', False, 'foo'),
        (False, 'true', 'foo', False, 'foo'),
    ])
    def test_set_text(self, use_js, editable, text, uses_js, arg):
        elem = get_webelem(attributes={'contenteditable': editable})
        elem.set_text(text, use_js=use_js)
        attr = 'evaluateJavaScript' if uses_js else 'setPlainText'
        called_mock = getattr(elem._elem, attr)
        called_mock.assert_called_with(arg)

    @pytest.mark.parametrize('with_cb', [True, False])
    def test_run_js_async(self, elem, with_cb):
        cb = mock.Mock(spec={}) if with_cb else None
        elem._elem.evaluateJavaScript.return_value = 42
        elem.run_js_async('the_answer();', cb)
        if with_cb:
            cb.assert_called_with(42)


class TestRemoveBlankTarget:

    @pytest.mark.parametrize('tagname', ['a', 'area'])
    @pytest.mark.parametrize('target', ['_self', '_parent', '_top', ''])
    def test_keep_target(self, tagname, target):
        elem = get_webelem(tagname=tagname, attributes={'target': target})
        elem.remove_blank_target()
        assert elem['target'] == target

    @pytest.mark.parametrize('tagname', ['a', 'area'])
    def test_no_target(self, tagname):
        elem = get_webelem(tagname=tagname)
        elem.remove_blank_target()
        assert 'target' not in elem

    @pytest.mark.parametrize('tagname', ['a', 'area'])
    def test_blank_target(self, tagname):
        elem = get_webelem(tagname=tagname, attributes={'target': '_blank'})
        elem.remove_blank_target()
        assert elem['target'] == '_top'

    @pytest.mark.parametrize('tagname', ['a', 'area'])
    def test_ancestor_blank_target(self, tagname):
        elem = get_webelem(tagname=tagname, attributes={'target': '_blank'})
        elem_child = get_webelem(tagname='img', parent=elem._elem)
        elem_child._elem.encloseWith(elem._elem)
        elem_child.remove_blank_target()
        assert elem['target'] == '_top'

    @pytest.mark.parametrize('depth', [1, 5, 10])
    def test_no_link(self, depth):
        elem = [None] * depth
        elem[0] = get_webelem(tagname='div')
        for i in range(1, depth):
            elem[i] = get_webelem(tagname='div', parent=elem[i-1]._elem)
            elem[i]._elem.encloseWith(elem[i-1]._elem)
        elem[-1].remove_blank_target()
        for i in range(depth):
            assert 'target' not in elem[i]


class TestIsVisible:

    @pytest.fixture
    def frame(self, stubs):
        return stubs.FakeWebFrame(QRect(0, 0, 100, 100))

    def test_invalid_frame_geometry(self, stubs):
        """Test with an invalid frame geometry."""
        rect = QRect(0, 0, 0, 0)
        assert not rect.isValid()
        frame = stubs.FakeWebFrame(rect)
        elem = get_webelem(QRect(0, 0, 10, 10), frame)
        assert not elem.is_visible(frame)

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

    @pytest.fixture
    def invalid_objects(self, stubs):
        """Set up the following base situation.

             0, 0                         300, 0
              ##############################
              #                            #
         0,10 # iframe  100,10             #
              #**********                  #
              #* e      * elems[0]: 10, 10 in iframe (visible)
              #*        *                  #
              #*        *                  #
              #**********                  #
        0,110 #.        .100,110           #
              #.        .                  #
              #. e      . elems[2]: 20,150 in iframe (not visible)
              #..........                  #
              ##############################
            300, 0                         300, 300

        Returns an Objects namedtuple with frame/iframe/elems attributes.
        """
        frame = stubs.FakeWebFrame(QRect(0, 0, 300, 300))
        iframe = stubs.FakeWebFrame(QRect(0, 10, 100, 100), parent=frame)
        assert frame.geometry().contains(iframe.geometry())

        elems = [
            get_webelem(QRect(10, 10, 0, 0), iframe),
            get_webelem(QRect(20, 150, 0, 0), iframe),
        ]
        for e in elems:
            assert not e.geometry().isValid()

        return self.Objects(frame=frame, iframe=iframe, elems=elems)

    def test_invalid_visible(self, invalid_objects):
        """Test elements with an invalid geometry which are visible.

        This seems to happen sometimes in the real world, with real elements
        which *are* visible, but don't have a valid geometry.
        """
        elem = invalid_objects.elems[0]
        assert elem.is_visible(invalid_objects.frame)

    def test_invalid_invisible(self, invalid_objects):
        """Test elements with an invalid geometry which are invisible."""
        assert not invalid_objects.elems[1].is_visible(invalid_objects.frame)


def test_focus_element(stubs):
    """Test getting focus element with a fake frame/element.

    Testing this with a real webpage is almost impossible because the window
    and the element would have focus, which is hard to achieve consistently in
    a test.
    """
    frame = stubs.FakeWebFrame(QRect(0, 0, 100, 100))
    elem = get_webelem()
    frame.focus_elem = elem._elem
    assert webkitelem.focus_elem(frame)._elem is elem._elem


class TestRectOnView:

    @pytest.fixture(autouse=True)
    def stubbed_config(self, config_stub, monkeypatch):
        """Add a zoom-text-only fake config value.

        This is needed for all the tests calling rect_on_view or is_visible.
        """
        config_stub.data = {'ui': {'zoom-text-only': 'true'}}
        monkeypatch.setattr('qutebrowser.browser.webkit.webkitelem.config',
                            config_stub)
        return config_stub

    @pytest.mark.parametrize('js_rect', [
        None,  # real geometry via getElementRects
        {},  # no geometry at all via getElementRects
        # unusable geometry via getElementRects
        {'length': '1', '0': {'width': 0, 'height': 0, 'x': 0, 'y': 0}},
    ])
    def test_simple(self, callback_checker, stubs, js_rect):
        geometry = QRect(5, 5, 4, 4)
        frame = stubs.FakeWebFrame(QRect(0, 0, 100, 100))
        elem = get_webelem(geometry, frame, js_rect_return=js_rect)
        elem.rect_on_view(callback=callback_checker.callback)
        callback_checker.check(QRect(5, 5, 4, 4))

    @pytest.mark.parametrize('js_rect', [None, {}])
    def test_scrolled(self, callback_checker, stubs, js_rect):
        geometry = QRect(20, 20, 4, 4)
        frame = stubs.FakeWebFrame(QRect(0, 0, 100, 100),
                                   scroll=QPoint(10, 10))
        elem = get_webelem(geometry, frame, js_rect_return=js_rect)
        elem.rect_on_view(callback=callback_checker.callback)
        callback_checker.check(QRect(20 - 10, 20 - 10, 4, 4))

    @pytest.mark.parametrize('js_rect', [None, {}])
    def test_iframe(self, callback_checker, stubs, js_rect):
        """Test an element in an iframe.

             0, 0                         200, 0
              ##############################
              #                            #
         0,10 # iframe  100,10             #
              #**********                  #
              #*        *                  #
              #*        *                  #
              #* e      * elem: 20,90 in iframe
              #**********                  #
        0,100 #                            #
              ##############################
            200, 0                         200, 200
        """
        frame = stubs.FakeWebFrame(QRect(0, 0, 200, 200))
        iframe = stubs.FakeWebFrame(QRect(0, 10, 100, 100), parent=frame)
        assert frame.geometry().contains(iframe.geometry())
        elem = get_webelem(QRect(20, 90, 10, 10), iframe,
                           js_rect_return=js_rect)
        elem.rect_on_view(callback=callback_checker.callback)
        callback_checker.check(QRect(20, 10 + 90, 10, 10))

    @pytest.mark.parametrize('js_rect', [None, {}])
    def test_passed_geometry(self, callback_checker, stubs, js_rect):
        """Make sure geometry isn't called when a geometry is passed."""
        frame = stubs.FakeWebFrame(QRect(0, 0, 200, 200))
        elem = get_webelem(frame=frame, js_rect_return=js_rect)
        rect = QRect(10, 20, 30, 40)
        elem.rect_on_view(elem_geometry=rect,
                          callback=callback_checker.callback)
        callback_checker.check(rect)
        assert not elem._elem.geometry.called

    @pytest.mark.parametrize('js_rect', [None, {}])
    @pytest.mark.parametrize('zoom_text_only', [True, False])
    def test_zoomed(self, callback_checker, stubs, config_stub, js_rect,
                    zoom_text_only):
        """Make sure the coordinates are adjusted when zoomed."""
        config_stub.data = {'ui': {'zoom-text-only': zoom_text_only}}
        geometry = QRect(10, 10, 4, 4)
        frame = stubs.FakeWebFrame(QRect(0, 0, 100, 100), zoom=0.5)
        elem = get_webelem(geometry, frame, js_rect_return=js_rect,
                           zoom_text_only=zoom_text_only)
        elem.rect_on_view(callback=callback_checker.callback)
        callback_checker.check(QRect(10, 10, 4, 4))


class TestGetChildFrames:

    """Check get_child_frames."""

    def test_single_frame(self, stubs):
        """Test get_child_frames with a single frame without children."""
        frame = stubs.FakeChildrenFrame()
        children = webkitelem.get_child_frames(frame)
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
        children = webkitelem.get_child_frames(parent)
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
        children = webkitelem.get_child_frames(root)
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
        monkeypatch.setattr('qutebrowser.browser.webkit.webkitelem.config',
                            config_stub)
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

        ('foobar', {}, False),
        ('foobar', {'contenteditable': 'true'}, True),
        ('foobar', {'contenteditable': 'false'}, False),
        ('foobar', {'contenteditable': 'true', 'disabled': None}, False),
        ('foobar', {'contenteditable': 'true', 'readonly': None}, False),

        ('foobar', {'role': 'foobar'}, False),
        ('foobar', {'role': 'combobox'}, True),
        ('foobar', {'role': 'textbox'}, True),
        ('foobar', {'role': 'combobox', 'disabled': None}, False),
        ('foobar', {'role': 'combobox', 'readonly': None}, False),
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
    def test_is_editable_div(self, classes, editable):
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
        (True, 'object', {}, False),
        (True, 'object', {'type': 'image/gif'}, False),
    ])
    def test_is_editable_plugin(self, stubbed_config, setting, tagname,
                                attributes, editable):
        stubbed_config.data['input']['insert-mode-on-plugins'] = setting
        elem = get_webelem(tagname=tagname, attributes=attributes)
        assert elem.is_editable() == editable


@pytest.mark.parametrize('attributes, expected', [
    # No attributes
    ({}, None),
    ({'href': 'foo'}, QUrl('http://www.example.com/foo')),
    ({'src': 'foo'}, QUrl('http://www.example.com/foo')),
    ({'href': 'foo', 'src': 'bar'}, QUrl('http://www.example.com/foo')),
    ({'href': '::garbage::'}, None),
    ({'href': 'http://www.example.org/'}, QUrl('http://www.example.org/')),
    ({'href': '  foo  '}, QUrl('http://www.example.com/foo')),
])
def test_resolve_url(attributes, expected):
    elem = get_webelem(attributes=attributes)
    baseurl = QUrl('http://www.example.com/')
    assert elem.resolve_url(baseurl) == expected


def test_resolve_url_relative_base():
    elem = get_webelem(attributes={'href': 'foo'})
    with pytest.raises(ValueError):
        elem.resolve_url(QUrl('base'))
