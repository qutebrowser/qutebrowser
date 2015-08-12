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

"""Utilities related to QWebElements.

Module attributes:
    Group: Enum for different kinds of groups.
    SELECTORS: CSS selectors for different groups of elements.
    FILTERS: A dictionary of filter functions for the modes.
             The filter for "links" filters javascript:-links and a-tags
             without "href".
"""

import collections.abc
import functools

from PyQt5.QtCore import QRect, QUrl
from PyQt5.QtWebKit import QWebElement

from qutebrowser.config import config
from qutebrowser.utils import log, usertypes, utils


Group = usertypes.enum('Group', ['all', 'links', 'images', 'url', 'prevnext',
                                 'focus'])


SELECTORS = {
    Group.all: ('a, area, textarea, select, input:not([type=hidden]), button, '
                'frame, iframe, link, [onclick], [onmousedown], [role=link], '
                '[role=option], [role=button], img'),
    Group.links: 'a, area, link, [role=link]',
    Group.images: 'img',
    Group.url: '[src], [href]',
    Group.prevnext: 'a, area, button, link, [role=button]',
    Group.focus: '*:focus',
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
        for name in ('addClass', 'appendInside', 'appendOutside',
                     'attributeNS', 'classes', 'clone', 'document',
                     'encloseContentsWith', 'encloseWith',
                     'evaluateJavaScript', 'findAll', 'findFirst',
                     'firstChild', 'geometry', 'hasAttributeNS',
                     'hasAttributes', 'hasClass', 'hasFocus', 'lastChild',
                     'localName', 'namespaceUri', 'nextSibling', 'parent',
                     'prefix', 'prependInside', 'prependOutside',
                     'previousSibling', 'removeAllChildren',
                     'removeAttributeNS', 'removeClass', 'removeFromDocument',
                     'render', 'replace', 'setAttributeNS', 'setFocus',
                     'setInnerXml', 'setOuterXml', 'setPlainText',
                     'setStyleProperty', 'styleProperty', 'tagName',
                     'takeFromDocument', 'toInnerXml', 'toOuterXml',
                     'toggleClass', 'webFrame', '__eq__', '__ne__'):
            # We don't wrap some methods for which we have better alternatives:
            #   - Mapping access for attributeNames/hasAttribute/setAttribute/
            #     attribute/removeAttribute.
            #   - isNull is checked automagically.
            #   - str(...) instead of toPlainText
            # For the rest, we create a wrapper which checks if the element is
            # null.

            method = getattr(self._elem, name)

            def _wrapper(meth, *args, **kwargs):
                # pylint: disable=missing-docstring
                self._check_vanished()
                return meth(*args, **kwargs)

            wrapper = functools.partial(_wrapper, method)
            # We used to do functools.update_wrapper here, but for some reason
            # when using hints with many links, this accounted for nearly 50%
            # of the time when profiling, which is unacceptable.
            setattr(self, name, wrapper)

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
            raise IsNullError('Element {} vanished!'.format(
                self._elem))

    def is_visible(self, mainframe):
        """Check whether the element is currently visible on the screen.

        Args:
            mainframe: The main QWebFrame.

        Return:
            True if the element is visible, False otherwise.
        """
        return is_visible(self._elem, mainframe)

    def rect_on_view(self):
        """Get the geometry of the element relative to the webview."""
        return rect_on_view(self._elem)

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
            return self['contenteditable'].lower() not in ('false', 'inherit')
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
        # pylint: disable=too-many-return-statements
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
        elif tag in ('embed', 'applet'):
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
        return self.get('role', None) in roles or tag in ('input', 'textarea')

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


def rect_on_view(elem, elem_geometry=None):
    """Get the geometry of the element relative to the webview.

    We need this as a standalone function (as opposed to a WebElementWrapper
    method) because we want to run is_visible before wrapping when hinting for
    performance reasons.

    Args:
        elem: The QWebElement to get the rect for.
        elem_geometry: The geometry of the element, or None.
                       Calling QWebElement::geometry is rather expensive so we
                       want to avoid doing it twice.
    """
    if elem.isNull():
        raise IsNullError("Got called on a null element!")
    if elem_geometry is None:
        elem_geometry = elem.geometry()
    frame = elem.webFrame()
    rect = QRect(elem_geometry)
    while frame is not None:
        rect.translate(frame.geometry().topLeft())
        rect.translate(frame.scrollPosition() * -1)
        frame = frame.parentFrame()
    return rect


def is_visible(elem, mainframe):
    """Check if the given element is visible in the frame.

    We need this as a standalone function (as opposed to a WebElementWrapper
    method) because we want to check this before wrapping when hinting for
    performance reasons.

    Args:
        elem: The QWebElement to check.
        mainframe: The QWebFrame in which the element should be visible.
    """
    if elem.isNull():
        raise IsNullError("Got called on a null element!")
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
        visible_on_screen = mainframe_geometry.contains(
            elem_rect.topLeft())
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
