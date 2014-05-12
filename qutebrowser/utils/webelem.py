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

import logging

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


def is_visible(elem):
    """Check whether the element is currently visible in its frame.

    Args:
        elem: The QWebElement to check.

    Return:
        True if the element is visible, False otherwise.
    """
    # FIXME we should also check if the frame is visible
    if elem.isNull():
        raise ValueError("Element is a null-element!")
    frame = elem.webFrame()
    rect = elem.geometry()
    if (not rect.isValid()) and rect.x() == 0:
        # Most likely an invisible link
        return False
    framegeom = frame.geometry()
    framegeom.moveTo(0, 0)
    framegeom.translate(frame.scrollPosition())
    if not framegeom.intersects(rect):
        # out of screen
        return False
    return True


def pos_on_screen(elem):
    """Get the position of the element on the screen."""
    # FIXME Instead of clicking the center, we could have nicer heuristics.
    # e.g. parse (-webkit-)border-radius correctly and click text fields at
    # the bottom right, and everything else on the top left or so.
    frame = elem.webFrame()
    pos = elem.geometry().center()
    while frame is not None:
        pos += frame.geometry().topLeft()
        logging.debug("After adding frame pos: {}".format(pos))
        pos -= frame.scrollPosition()
        logging.debug("After removing frame scrollpos: {}".format(pos))
        frame = frame.parentFrame()
    return pos


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


def get_child_frames(startframe):
    """Get all children recursively of a given QWebFrame.

    Loosly based on http://blog.nextgenetics.net/?e=64

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
