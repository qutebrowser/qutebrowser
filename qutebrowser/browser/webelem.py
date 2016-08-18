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

"""Generic web element related code.

Module attributes:
    Group: Enum for different kinds of groups.
    SELECTORS: CSS selectors for different groups of elements.
    FILTERS: A dictionary of filter functions for the modes.
             The filter for "links" filters javascript:-links and a-tags
             without "href".
"""

import collections.abc

from PyQt5.QtCore import QUrl

from qutebrowser.config import config
from qutebrowser.utils import log, usertypes, utils, qtutils


Group = usertypes.enum('Group', ['all', 'links', 'images', 'url', 'prevnext',
                                 'inputs'])


SELECTORS = {
    Group.all: ('a, area, textarea, select, input:not([type=hidden]), button, '
                'frame, iframe, link, [onclick], [onmousedown], [role=link], '
                '[role=option], [role=button], img'),
    Group.links: 'a, area, link, [role=link]',
    Group.images: 'img',
    Group.url: '[src], [href]',
    Group.prevnext: 'a, area, button, link, [role=button]',
    Group.inputs: ('input[type=text], input[type=email], input[type=url], '
                   'input[type=tel], input[type=number], '
                   'input[type=password], input[type=search], '
                   'input:not([type]), textarea'),
}


def filter_links(elem):
    return 'href' in elem and QUrl(elem['href']).scheme() != 'javascript'


FILTERS = {
    Group.links: filter_links,
    Group.prevnext: filter_links,
}


class Error(Exception):

    """Base class for WebElement errors."""

    pass


class AbstractWebElement(collections.abc.MutableMapping):

    """A wrapper around QtWebKit/QtWebEngine web element."""

    def __eq__(self, other):
        raise NotImplementedError

    def __str__(self):
        return self.text()

    def __getitem__(self, key):
        raise NotImplementedError

    def __setitem__(self, key, val):
        raise NotImplementedError

    def __delitem__(self, key):
        raise NotImplementedError

    def __iter__(self):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    def __repr__(self):
        try:
            html = self.debug_text()
        except Error:
            html = None
        return utils.get_repr(self, html=html)

    def has_frame(self):
        """Check if this element has a valid frame attached."""
        raise NotImplementedError

    def geometry(self):
        """Get the geometry for this element."""
        raise NotImplementedError

    def style_property(self, name, *, strategy):
        """Get the element style resolved with the given strategy."""
        raise NotImplementedError

    def classes(self):
        """Get a list of classes assigned to this element."""
        raise NotImplementedError

    def tag_name(self):
        """Get the tag name of this element.

        The returned name will always be lower-case.
        """
        raise NotImplementedError

    def outer_xml(self):
        """Get the full HTML representation of this element."""
        raise NotImplementedError

    def text(self, *, use_js=False):
        """Get the plain text content for this element.

        Args:
            use_js: Whether to use javascript if the element isn't
                    content-editable.
        """
        # FIXME:qtwebengine what to do about use_js with WebEngine?
        raise NotImplementedError

    def set_text(self, text, *, use_js=False):
        """Set the given plain text.

        Args:
            use_js: Whether to use javascript if the element isn't
                    content-editable.
        """
        # FIXME:qtwebengine what to do about use_js with WebEngine?
        raise NotImplementedError

    def run_js_async(self, code, callback=None):
        """Run the given JS snippet async on the element."""
        # FIXME:qtwebengine get rid of this?
        raise NotImplementedError

    def parent(self):
        """Get the parent element of this element."""
        # FIXME:qtwebengine get rid of this?
        raise NotImplementedError

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
        raise NotImplementedError

    def is_visible(self, mainframe):
        """Check if the given element is visible in the given frame."""
        # FIXME:qtwebengine get rid of this?
        raise NotImplementedError

    def is_writable(self):
        """Check whether an element is writable."""
        return not ('disabled' in self or 'readonly' in self)

    def is_content_editable(self):
        """Check if an element has a contenteditable attribute.

        Args:
            elem: The QWebElement to check.

        Return:
            True if the element has a contenteditable attribute,
            False otherwise.
        """
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
        for klass in self.classes():
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
        roles = ('combobox', 'textbox')
        log.misc.debug("Checking if element is editable: {}".format(
            repr(self)))
        tag = self.tag_name()
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
        roles = ('combobox', 'textbox')
        tag = self.tag_name()
        return self.get('role', None) in roles or tag in ['input', 'textarea']

    def remove_blank_target(self):
        """Remove target from link."""
        elem = self
        for _ in range(5):
            if elem is None:
                break
            tag = elem.tag_name()
            if tag == 'a' or tag == 'area':
                if elem.get('target', None) == '_blank':
                    elem['target'] = '_top'
                break
            elem = elem.parent()

    def debug_text(self):
        """Get a text based on an element suitable for debug output."""
        return utils.compact_text(self.outer_xml(), 500)

    def resolve_url(self, baseurl):
        """Resolve the URL in the element's src/href attribute.

        Args:
            baseurl: The URL to base relative URLs on as QUrl.

        Return:
            A QUrl with the absolute URL, or None.
        """
        if baseurl.isRelative():
            raise ValueError("Need an absolute base URL!")

        for attr in ['href', 'src']:
            if attr in self:
                text = self[attr].strip()
                break
        else:
            return None

        url = QUrl(text)
        if not url.isValid():
            return None
        if url.isRelative():
            url = baseurl.resolved(url)
        qtutils.ensure_valid(url)
        return url
