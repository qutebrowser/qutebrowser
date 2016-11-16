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

"""QtWebKit specific part of the web element API."""

from PyQt5.QtCore import QRect
from PyQt5.QtWebKit import QWebElement

from qutebrowser.config import config
from qutebrowser.utils import log, utils, javascript
from qutebrowser.browser import webelem


class IsNullError(webelem.Error):

    """Gets raised by WebKitElement if an element is null."""

    pass


class WebKitElement(webelem.AbstractWebElement):

    """A wrapper around a QWebElement."""

    def __init__(self, elem, tab):
        super().__init__(tab)
        if isinstance(elem, self.__class__):
            raise TypeError("Trying to wrap a wrapper!")
        if elem.isNull():
            raise IsNullError('{} is a null element!'.format(elem))
        self._elem = elem

    def __str__(self):
        self._check_vanished()
        return self._elem.toPlainText()

    def __eq__(self, other):
        if not isinstance(other, WebKitElement):
            return NotImplemented
        return self._elem == other._elem  # pylint: disable=protected-access

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

    def has_frame(self):
        self._check_vanished()
        return self._elem.webFrame() is not None

    def geometry(self):
        self._check_vanished()
        return self._elem.geometry()

    def style_property(self, name, *, strategy):
        self._check_vanished()
        strategies = {
            # FIXME:qtwebengine which ones do we actually need?
            'inline': QWebElement.InlineStyle,
            'computed': QWebElement.ComputedStyle,
        }
        qt_strategy = strategies[strategy]
        return self._elem.styleProperty(name, qt_strategy)

    def classes(self):
        self._check_vanished()
        return self._elem.classes()

    def tag_name(self):
        """Get the tag name for the current element."""
        self._check_vanished()
        return self._elem.tagName().lower()

    def outer_xml(self):
        """Get the full HTML representation of this element."""
        self._check_vanished()
        return self._elem.toOuterXml()

    def value(self):
        self._check_vanished()
        return self._elem.evaluateJavaScript('this.value')

    def set_value(self, value):
        self._check_vanished()
        if self.is_content_editable():
            log.webelem.debug("Filling {!r} via set_text.".format(self))
            self._elem.setPlainText(value)
        else:
            log.webelem.debug("Filling {!r} via javascript.".format(self))
            value = javascript.string_escape(value)
            self._elem.evaluateJavaScript("this.value='{}'".format(value))

    def insert_text(self, text):
        self._check_vanished()
        if not self.is_editable(strict=True):
            raise webelem.Error("Element is not editable!")
        log.webelem.debug("Inserting text into element {!r}".format(self))
        self._elem.evaluateJavaScript("""
            var text = "{}";
            var event = document.createEvent("TextEvent");
            event.initTextEvent("textInput", true, true, null, text);
            this.dispatchEvent(event);
        """.format(javascript.string_escape(text)))

    def _parent(self):
        """Get the parent element of this element."""
        self._check_vanished()
        elem = self._elem.parent()
        if elem is None or elem.isNull():
            return None
        return WebKitElement(elem, tab=self._tab)

    def _rect_on_view_js(self):
        """Javascript implementation for rect_on_view."""
        # FIXME:qtwebengine maybe we can reuse this?
        rects = self._elem.evaluateJavaScript("this.getClientRects()")
        if rects is None:  # pragma: no cover
            # On e.g. Void Linux with musl libc, the stack size is too small
            # for jsc, and running JS will fail. If that happens, fall back to
            # the Python implementation.
            # https://github.com/The-Compiler/qutebrowser/issues/1641
            return None

        text = utils.compact_text(self._elem.toOuterXml(), 500)
        log.webelem.vdebug("Client rectangles of element '{}': {}".format(
            text, rects))

        for i in range(int(rects.get("length", 0))):
            rect = rects[str(i)]
            width = rect.get("width", 0)
            height = rect.get("height", 0)
            if width > 1 and height > 1:
                # fix coordinates according to zoom level
                zoom = self._elem.webFrame().zoomFactor()
                if not config.get('ui', 'zoom-text-only'):
                    rect["left"] *= zoom
                    rect["top"] *= zoom
                    width *= zoom
                    height *= zoom
                rect = QRect(rect["left"], rect["top"], width, height)
                frame = self._elem.webFrame()
                while frame is not None:
                    # Translate to parent frames' position (scroll position
                    # is taken care of inside getClientRects)
                    rect.translate(frame.geometry().topLeft())
                    frame = frame.parentFrame()
                return rect

        return None

    def _rect_on_view_python(self, elem_geometry):
        """Python implementation for rect_on_view."""
        if elem_geometry is None:
            geometry = self._elem.geometry()
        else:
            geometry = elem_geometry
        frame = self._elem.webFrame()
        rect = QRect(geometry)
        while frame is not None:
            rect.translate(frame.geometry().topLeft())
            rect.translate(frame.scrollPosition() * -1)
            frame = frame.parentFrame()
        return rect

    def rect_on_view(self, *, elem_geometry=None, no_js=False):
        """Get the geometry of the element relative to the webview.

        Uses the getClientRects() JavaScript method to obtain the collection of
        rectangles containing the element and returns the first rectangle which
        is large enough (larger than 1px times 1px). If all rectangles returned
        by getClientRects() are too small, falls back to elem.rect_on_view().

        Skipping of small rectangles is due to <a> elements containing other
        elements with "display:block" style, see
        https://github.com/The-Compiler/qutebrowser/issues/1298

        Args:
            elem_geometry: The geometry of the element, or None.
                           Calling QWebElement::geometry is rather expensive so
                           we want to avoid doing it twice.
            no_js: Fall back to the Python implementation
        """
        self._check_vanished()

        # First try getting the element rect via JS, as that's usually more
        # accurate
        if elem_geometry is None and not no_js:
            rect = self._rect_on_view_js()
            if rect is not None:
                return rect

        # No suitable rects found via JS, try via the QWebElement API
        return self._rect_on_view_python(elem_geometry)

    def _is_visible(self, mainframe):
        """Check if the given element is visible in the given frame.

        This is not public API because it can't be implemented easily here with
        QtWebEngine, and is only used via find_css(..., only_visible=True) via
        the tab API.
        """
        self._check_vanished()
        # CSS attributes which hide an element
        hidden_attributes = {
            'visibility': 'hidden',
            'display': 'none',
        }
        for k, v in hidden_attributes.items():
            if self._elem.styleProperty(k, QWebElement.ComputedStyle) == v:
                return False
        elem_geometry = self._elem.geometry()
        if not elem_geometry.isValid() and elem_geometry.x() == 0:
            # Most likely an invisible link
            return False
        # First check if the element is visible on screen
        elem_rect = self.rect_on_view(elem_geometry=elem_geometry)
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
        elem_frame = self._elem.webFrame()
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

    def remove_blank_target(self):
        elem = self
        for _ in range(5):
            if elem is None:
                break
            tag = elem.tag_name()
            if tag == 'a' or tag == 'area':
                if elem.get('target', None) == '_blank':
                    elem['target'] = '_top'
                break
            elem = elem._parent()  # pylint: disable=protected-access


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
