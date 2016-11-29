# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

# FIXME:qtwebengine remove this once the stubs are gone
# pylint: disable=unused-variable

"""QtWebEngine specific part of the web element API."""

from PyQt5.QtCore import QRect

from qutebrowser.utils import log, javascript
from qutebrowser.browser import webelem


class WebEngineElement(webelem.AbstractWebElement):

    """A web element for QtWebEngine, using JS under the hood."""

    def __init__(self, js_dict, tab):
        super().__init__(tab)
        self._id = js_dict['id']
        self._js_dict = js_dict

    def __str__(self):
        return self._js_dict.get('text', '')

    def __eq__(self, other):
        if not isinstance(other, WebEngineElement):
            return NotImplemented
        return self._id == other._id  # pylint: disable=protected-access

    def __getitem__(self, key):
        attrs = self._js_dict['attributes']
        return attrs[key]

    def __setitem__(self, key, val):
        self._js_dict['attributes'][key] = val
        js_code = javascript.assemble('webelem', 'set_attribute', self._id,
            key, val)
        self._tab.run_js_async(js_code)

    def __delitem__(self, key):
        log.stub()

    def __iter__(self):
        return iter(self._js_dict['attributes'])

    def __len__(self):
        return len(self._js_dict['attributes'])

    def has_frame(self):
        return True

    def geometry(self):
        log.stub()
        return QRect()

    def style_property(self, name, *, strategy):
        log.stub()
        return ''

    def classes(self):
        """Get a list of classes assigned to this element."""
        return self._js_dict['class_name'].split()

    def tag_name(self):
        """Get the tag name of this element.

        The returned name will always be lower-case.
        """
        return self._js_dict['tag_name'].lower()

    def outer_xml(self):
        """Get the full HTML representation of this element."""
        return self._js_dict['outer_xml']

    def value(self):
        return self._js_dict.get('value', None)

    def set_value(self, value):
        js_code = javascript.assemble('webelem', 'set_value', self._id, value)
        self._tab.run_js_async(js_code)

    def insert_text(self, text):
        if not self.is_editable(strict=True):
            raise webelem.Error("Element is not editable!")
        log.webelem.debug("Inserting text into element {!r}".format(self))
        js_code = javascript.assemble('webelem', 'insert_text', self._id, text)
        self._tab.run_js_async(js_code)

    def rect_on_view(self, *, elem_geometry=None, no_js=False):
        """Get the geometry of the element relative to the webview.

        Skipping of small rectangles is due to <a> elements containing other
        elements with "display:block" style, see
        https://github.com/The-Compiler/qutebrowser/issues/1298

        Args:
            elem_geometry: The geometry of the element, or None.
                           Calling QWebElement::geometry is rather expensive so
                           we want to avoid doing it twice.
            no_js: Fall back to the Python implementation
        """
        rects = self._js_dict['rects']
        for rect in rects:
            # FIXME:qtwebengine
            # width = rect.get("width", 0)
            # height = rect.get("height", 0)
            width = rect['width']
            height = rect['height']
            left = rect['left']
            top = rect['top']
            if width > 1 and height > 1:
                # Fix coordinates according to zoom level
                # We're not checking for zoom-text-only here as that doesn't
                # exist for QtWebEngine.
                zoom = self._tab.zoom.factor()
                rect = QRect(left * zoom, top * zoom,
                             width * zoom, height * zoom)
                # FIXME:qtwebengine
                # frame = self._elem.webFrame()
                # while frame is not None:
                #     # Translate to parent frames' position (scroll position
                #     # is taken care of inside getClientRects)
                #     rect.translate(frame.geometry().topLeft())
                #     frame = frame.parentFrame()
                return rect
        log.webelem.debug("Couldn't find rectangle for {!r} ({})".format(
            self, rects))
        return QRect()

    def remove_blank_target(self):
        js_code = javascript.assemble('webelem', 'remove_blank_target',
            self._id)
        self._tab.run_js_async(js_code)
