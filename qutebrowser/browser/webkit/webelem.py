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

"""Utilities related to QWebElements.

Module attributes:
    Group: Enum for different kinds of groups.
    SELECTORS: CSS selectors for different groups of elements.
    FILTERS: A dictionary of filter functions for the modes.
             The filter for "links" filters javascript:-links and a-tags
             without "href".
"""

import collections.abc

from PyQt5.QtCore import QRect, QUrl
from PyQt5.QtWebKit import QWebElement

from qutebrowser.config import config
from qutebrowser.utils import log, usertypes, utils


Group = usertypes.enum('Group', ['all', 'links', 'images', 'url', 'prevnext',
                                 'focus', 'inputs'])


SELECTORS = {
    Group.all: ('a, area, textarea, select, input:not([type=hidden]), button, '
                'frame, iframe, link, [onclick], [onmousedown], [role=link], '
                '[role=option], [role=button], img'),
    Group.links: 'a, area, link, [role=link]',
    Group.images: 'img',
    Group.url: '[src], [href]',
    Group.prevnext: 'a, area, button, link, [role=button]',
    Group.focus: '*:focus',
    Group.inputs: ('input[type=text], input[type=email], input[type=url], '
                   'input[type=tel], input[type=number], '
                   'input[type=password], input[type=search], textarea'),
}


def filter_links(elem):
    return 'href' in elem and QUrl(elem['href']).scheme() != 'javascript'


FILTERS = {
    Group.links: filter_links,
    Group.prevnext: filter_links,
}


class IsNullError(Exception):

    """Gets raised by WebElementWrapper if an element is null."""

    pass


class WebElementWrapper(collections.abc.MutableMapping):

    """A wrapper around QWebElement to make it more intelligent."""

    def __init__(self, elem):
        if isinstance(elem, self.__class__):
            raise TypeError("Trying to wrap a wrapper!")
        if elem.isNull():
            raise IsNullError('{} is a null element!'.format(elem))
        self._elem = elem

    def __str__(self):
        self._check_vanished()
        return self._elem.toPlainText()

    def __repr__(self):
        try:
            html = self.debug_text()
        except IsNullError:
            html = None
        return utils.get_repr(self, html=html)

    def __getitem__(self, key):
        self._check_vanished()
        if key not in self:
            raise KeyError(key)
        return self._elem.attribute(key)

    def __setitem__(self, key, val):
        self._check_vanished()
        self._elem.setAttribute(key, val)

    def __delitem__(self, key):
        self._check_vanished()
        if key not in self:
            raise KeyError(key)
        self._elem.removeAttribute(key)

    def __contains__(self, key):
        self._check_vanished()
        return self._elem.hasAttribute(key)

    def __iter__(self):
        self._check_vanished()
        yield from self._elem.attributeNames()

    def __len__(self):
        self._check_vanished()
        return len(self._elem.attributeNames())

    def _check_vanished(self):
        """Raise an exception if the element vanished (is null)."""
        if self._elem.isNull():
            raise IsNullError('Element {} vanished!'.format(self._elem))

    def frame(self):
        """Get the main frame of this element."""
        # FIXME:qtwebengine how to get rid of this?
        self._check_vanished()
        return self._elem.webFrame()

    def geometry(self):
        """Get the geometry for this element."""
        self._check_vanished()
        return self._elem.geometry()

    def document_element(self):
        """Get the document element of this element."""
        self._check_vanished()
        elem = self._elem.webFrame().documentElement()
        return WebElementWrapper(elem)

    def create_inside(self, tagname):
        """Append the given element inside the current one."""
        # It seems impossible to create an empty QWebElement for which isNull()
        # is false so we can work with it.
        # As a workaround, we use appendInside() with markup as argument, and
        # then use lastChild() to get a reference to it.
        # See: http://stackoverflow.com/q/7364852/2085149
        self._check_vanished()
        self._elem.appendInside('<{}></{}>'.format(tagname, tagname))
        return WebElementWrapper(self._elem.lastChild())

    def find_first(self, selector):
        """Find the first child based on the given CSS selector."""
        self._check_vanished()
        elem = self._elem.findFirst(selector)
        if elem.isNull():
            return None
        return WebElementWrapper(elem)

    def style_property(self, name, strategy):
        """Get the element style resolved with the given strategy."""
        self._check_vanished()
        return self._elem.styleProperty(name, strategy)

    def set_text(self, text):
        """Set the given plain text."""
        self._check_vanished()
        if self.is_content_editable():
            log.misc.debug("Filling element {} via set_text.".format(
                self.debug_text()))
            self._elem.setPlainText(text)
        else:
            log.misc.debug("Filling element {} via javascript.".format(
                self.debug_text()))
            text = javascript_escape(text)
            self._elem.evaluateJavaScript("this.value='{}'".format(text))

    def set_inner_xml(self, xml):
        """Set the given inner XML."""
        self._check_vanished()
        self._elem.setInnerXml(xml)

    def remove_from_document(self):
        """Remove the node from the document."""
        self._check_vanished()
        self._elem.removeFromDocument()

    def set_style_property(self, name, value):
        """Set the element style."""
        self._check_vanished()
        return self._elem.setStyleProperty(name, value)

    def is_visible(self):
        """Check whether the element is currently visible on the screen.

        Return:
            True if the element is visible, False otherwise.
        """
        return is_visible(self._elem)

    def rect_on_view(self, **kwargs):
        """Get the geometry of the element relative to the webview."""
        return rect_on_view(self._elem, **kwargs)

    def is_writable(self):
        """Check whether an element is writable."""
        self._check_vanished()
        return not ('disabled' in self or 'readonly' in self)

    def is_content_editable(self):
        """Check if an element has a contenteditable attribute.

        Args:
            elem: The QWebElement to check.

        Return:
            True if the element has a contenteditable attribute,
            False otherwise.
        """
        self._check_vanished()
        try:
            return self['contenteditable'].lower() not in ['false', 'inherit']
        except KeyError:
            return False

    def _is_editable_object(self):
        """Check if an object-element is editable."""
        if 'type' not in self:
            log.webview.debug("<object> without type clicked...")
            return False
        objtype = self['type'].lower()
        if objtype.startswith('application/') or 'classid' in self:
            # Let's hope flash/java stuff has an application/* mimetype OR
            # at least a classid attribute. Oh, and let's hope images/...
            # DON'T have a classid attribute. HTML sucks.
            log.webview.debug("<object type='{}'> clicked.".format(objtype))
            return config.get('input', 'insert-mode-on-plugins')
        else:
            # Image/Audio/...
            return False

    def _is_editable_input(self):
        """Check if an input-element is editable.

        Return:
            True if the element is editable, False otherwise.
        """
        try:
            objtype = self['type'].lower()
        except KeyError:
            return self.is_writable()
        else:
            if objtype in ['text', 'email', 'url', 'tel', 'number', 'password',
                           'search']:
                return self.is_writable()
            else:
                return False

    def _is_editable_div(self):
        """Check if a div-element is editable.

        Return:
            True if the element is editable, False otherwise.
        """
        # Beginnings of div-classes which are actually some kind of editor.
        div_classes = ('CodeMirror',  # Javascript editor over a textarea
                       'kix-',        # Google Docs editor
                       'ace_')        # http://ace.c9.io/
        for klass in self._elem.classes():
            if any([klass.startswith(e) for e in div_classes]):
                return True
        return False

    def is_editable(self, strict=False):
        """Check whether we should switch to insert mode for this element.

        Args:
            strict: Whether to do stricter checking so only fields where we can
                    get the value match, for use with the :editor command.

        Return:
            True if we should switch to insert mode, False otherwise.
        """
        self._check_vanished()
        roles = ('combobox', 'textbox')
        log.misc.debug("Checking if element is editable: {}".format(
            repr(self)))
        tag = self._elem.tagName().lower()
        if self.is_content_editable() and self.is_writable():
            return True
        elif self.get('role', None) in roles and self.is_writable():
            return True
        elif tag == 'input':
            return self._is_editable_input()
        elif tag == 'textarea':
            return self.is_writable()
        elif tag in ['embed', 'applet']:
            # Flash/Java/...
            return config.get('input', 'insert-mode-on-plugins') and not strict
        elif tag == 'object':
            return self._is_editable_object() and not strict
        elif tag == 'div':
            return self._is_editable_div() and not strict
        else:
            return False

    def is_text_input(self):
        """Check if this element is some kind of text box."""
        self._check_vanished()
        roles = ('combobox', 'textbox')
        tag = self._elem.tagName().lower()
        return self.get('role', None) in roles or tag in ['input', 'textarea']

    def remove_blank_target(self):
        """Remove target from link."""
        elem = self._elem
        for _ in range(5):
            if elem is None:
                break
            tag = elem.tagName().lower()
            if tag == 'a' or tag == 'area':
                if elem.attribute('target') == '_blank':
                    elem.setAttribute('target', '_top')
                break
            elem = elem.parent()

    def debug_text(self):
        """Get a text based on an element suitable for debug output."""
        self._check_vanished()
        return utils.compact_text(self._elem.toOuterXml(), 500)


def javascript_escape(text):
    """Escape values special to javascript in strings.

    With this we should be able to use something like:
      elem.evaluateJavaScript("this.value='{}'".format(javascript_escape(...)))
    And all values should work.
    """
    # This is a list of tuples because order matters, and using OrderedDict
    # makes no sense because we don't actually need dict-like properties.
    replacements = (
        ('\\', r'\\'),  # First escape all literal \ signs as \\.
        ("'", r"\'"),   # Then escape ' and " as \' and \".
        ('"', r'\"'),   # (note it won't hurt when we escape the wrong one).
        ('\n', r'\n'),  # We also need to escape newlines for some reason.
        ('\r', r'\r'),
        ('\x00', r'\x00'),
        ('\ufeff', r'\ufeff'),
        # http://stackoverflow.com/questions/2965293/
        ('\u2028', r'\u2028'),
        ('\u2029', r'\u2029'),
    )
    for orig, repl in replacements:
        text = text.replace(orig, repl)
    return text


def get_child_frames(startframe):
    """Get all children recursively of a given QWebFrame.

    Loosely based on http://blog.nextgenetics.net/?e=64

    Args:
        startframe: The QWebFrame to start with.

    Return:
        A list of children QWebFrame, or an empty list.
    """
    results = []
    frames = [startframe]
    while frames:
        new_frames = []
        for frame in frames:
            results.append(frame)
            new_frames += frame.childFrames()
        frames = new_frames
    return results


def focus_elem(frame):
    """Get the focused element in a web frame.

    Args:
        frame: The QWebFrame to search in.
    """
    elem = frame.findFirstElement(SELECTORS[Group.focus])
    return WebElementWrapper(elem)


def rect_on_view(elem, *, elem_geometry=None, adjust_zoom=True, no_js=False):
    """Get the geometry of the element relative to the webview.

    We need this as a standalone function (as opposed to a WebElementWrapper
    method) because we want to run is_visible before wrapping when hinting for
    performance reasons.

    Uses the getClientRects() JavaScript method to obtain the collection of
    rectangles containing the element and returns the first rectangle which is
    large enough (larger than 1px times 1px). If all rectangles returned by
    getClientRects() are too small, falls back to elem.rect_on_view().

    Skipping of small rectangles is due to <a> elements containing other
    elements with "display:block" style, see
    https://github.com/The-Compiler/qutebrowser/issues/1298

    Args:
        elem: The QWebElement to get the rect for.
        elem_geometry: The geometry of the element, or None.
                       Calling QWebElement::geometry is rather expensive so we
                       want to avoid doing it twice.
        adjust_zoom: Whether to adjust the element position based on the
                     current zoom level.
        no_js: Fall back to the Python implementation
    """
    if elem.isNull():
        raise IsNullError("Got called on a null element!")

    # First try getting the element rect via JS, as that's usually more
    # accurate
    if elem_geometry is None and not no_js:
        rects = elem.evaluateJavaScript("this.getClientRects()")
        text = utils.compact_text(elem.toOuterXml(), 500)
        log.hints.vdebug("Client rectangles of element '{}': {}".format(text,
                                                                        rects))
        for i in range(int(rects.get("length", 0))):
            rect = rects[str(i)]
            width = rect.get("width", 0)
            height = rect.get("height", 0)
            if width > 1 and height > 1:
                # fix coordinates according to zoom level
                zoom = elem.webFrame().zoomFactor()
                if not config.get('ui', 'zoom-text-only') and adjust_zoom:
                    rect["left"] *= zoom
                    rect["top"] *= zoom
                    width *= zoom
                    height *= zoom
                rect = QRect(rect["left"], rect["top"], width, height)
                frame = elem.webFrame()
                while frame is not None:
                    # Translate to parent frames' position
                    # (scroll position is taken care of inside getClientRects)
                    rect.translate(frame.geometry().topLeft())
                    frame = frame.parentFrame()
                return rect

    # No suitable rects found via JS, try via the QWebElement API
    if elem_geometry is None:
        geometry = elem.geometry()
    else:
        geometry = elem_geometry
    frame = elem.webFrame()
    rect = QRect(geometry)
    while frame is not None:
        rect.translate(frame.geometry().topLeft())
        rect.translate(frame.scrollPosition() * -1)
        frame = frame.parentFrame()
    # We deliberately always adjust the zoom here, even with adjust_zoom=False
    if elem_geometry is None:
        zoom = elem.webFrame().zoomFactor()
        if not config.get('ui', 'zoom-text-only'):
            rect.moveTo(rect.left() / zoom, rect.top() / zoom)
            rect.setWidth(rect.width() / zoom)
            rect.setHeight(rect.height() / zoom)
    return rect


def is_visible(elem):
    """Check if the given element is visible in the frame.

    We need this as a standalone function (as opposed to a WebElementWrapper
    method) because we want to check this before wrapping when hinting for
    performance reasons.

    Args:
        elem: The QWebElement to check.
    """
    if elem.isNull():
        raise IsNullError("Got called on a null element!")
    mainframe = elem.webFrame()
    # CSS attributes which hide an element
    hidden_attributes = {
        'visibility': 'hidden',
        'display': 'none',
    }
    for k, v in hidden_attributes.items():
        if elem.styleProperty(k, QWebElement.ComputedStyle) == v:
            return False
    elem_geometry = elem.geometry()
    if not elem_geometry.isValid() and elem_geometry.x() == 0:
        # Most likely an invisible link
        return False
    # First check if the element is visible on screen
    elem_rect = rect_on_view(elem, elem_geometry=elem_geometry)
    mainframe_geometry = mainframe.geometry()
    if elem_rect.isValid():
        visible_on_screen = mainframe_geometry.intersects(elem_rect)
    else:
        # We got an invalid rectangle (width/height 0/0 probably), but this
        # can still be a valid link.
        visible_on_screen = mainframe_geometry.contains(elem_rect.topLeft())
    # Then check if it's visible in its frame if it's not in the main
    # frame.
    elem_frame = elem.webFrame()
    framegeom = QRect(elem_frame.geometry())
    if not framegeom.isValid():
        visible_in_frame = False
    elif elem_frame.parentFrame() is not None:
        framegeom.moveTo(0, 0)
        framegeom.translate(elem_frame.scrollPosition())
        if elem_geometry.isValid():
            visible_in_frame = framegeom.intersects(elem_geometry)
        else:
            # We got an invalid rectangle (width/height 0/0 probably), but
            # this can still be a valid link.
            visible_in_frame = framegeom.contains(elem_geometry.topLeft())
    else:
        visible_in_frame = visible_on_screen
    return all([visible_on_screen, visible_in_frame])
