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

"""Utilities related to QWebElements.

Module attributes:
    Group: Enum for different kinds of groups.
    SELECTORS: CSS selectors for different groups of elements.
    FILTERS: A dictionary of filter functions for the modes.
             The filter for "links" filters javascript:-links and a-tags
             without "href".
"""

import qutebrowser.utils.url as urlutils
from qutebrowser.utils.usertypes import enum


Group = enum('all', 'links', 'images', 'editable', 'url', 'prevnext_rel',
             'prevnext', 'editable_focused')


SELECTORS = {
    Group.all: ('a, textarea, select, input:not([type=hidden]), button, '
                'frame, iframe, [onclick], [onmousedown], [role=link], '
                '[role=option], [role=button], img'),
    Group.links: 'a',
    Group.images: 'img',
    Group.editable: ('input[type=text], input[type=email], input[type=url], '
                     'input[type=tel], input[type=number], '
                     'input[type=password], input[type=search], textarea'),
    Group.url: '[src], [href]',
    Group.prevnext_rel: 'link, [role=link]',
    Group.prevnext: 'a, button, [role=button]',
}

SELECTORS[Group.editable_focused] = ', '.join(
    [sel.strip() + ':focus' for sel in SELECTORS[Group.editable].split(',')])

FILTERS = {
    Group.links: (lambda e: e.hasAttribute('href') and
                  urlutils.qurl(e.attribute('href')).scheme() != 'javascript'),
}


def is_visible(e, frame=None):
    """Check whether the element is currently visible in its frame.

    Args:
        e: The QWebElement to check.
        frame: The QWebFrame in which the element should be visible in.
               If None, the element's frame is used.

    Return:
        True if the element is visible, False otherwise.
    """
    if e.isNull():
        raise ValueError("Element is a null-element!")
    if frame is None:
        frame = e.webFrame()
    rect = e.geometry()
    if (not rect.isValid()) and rect.x() == 0:
        # Most likely an invisible link
        return False
    framegeom = frame.geometry()
    framegeom.translate(frame.scrollPosition())
    if not framegeom.contains(rect.topLeft()):
        # out of screen
        return False
    return True


def javascript_escape(text):
    """Escape values special to javascript in strings.

    This maybe makes them work with QWebElement::evaluateJavaScript.
    Maybe.
    """
    # This is a list of tuples because order matters, and using OrderedDict
    # makes no sense because we don't actually need dict-like properties.
    replacements = [
        ('\\', r'\\'),
        ('\n', r'\n'),
        ('\t', r'\t'),
        ("'", r"\'"),
        ('"', r'\"'),
    ]
    text = text.rstrip('\n')
    for orig, repl in replacements:
        text = text.replace(orig, repl)
    return text
