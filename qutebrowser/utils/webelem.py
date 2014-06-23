# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

from PyQt5.QtCore import QRect, QUrl
from PyQt5.QtWebKit import QWebElement

import qutebrowser.utils.log as log
from qutebrowser.utils.usertypes import enum
import qutebrowser.config.config as config


Group = enum('all', 'links', 'images', 'editable', 'url', 'prevnext_rel',
             'prevnext', 'editable_focused')


SELECTORS = {
    Group.all: ('a, textarea, select, input:not([type=hidden]), button, '
                'frame, iframe, [onclick], [onmousedown], [role=link], '
                '[role=option], [role=button], img'),
    Group.links: 'a',
    Group.images: 'img',
    # This doesn't contain all the groups where we should switch to insert mode
    # - it is just used when opening the external editor.
    Group.editable_focused: ('input[type=text]:focus, '
                             'input[type=email]:focus, '
                             'input[type=url]:focus, '
                             'input[type=tel]:focus, '
                             'input[type=number]:focus, '
                             'input[type=password]:focus, '
                             'input[type=search]:focus, '
                             'textarea:focus'),
    Group.url: '[src], [href]',
    Group.prevnext_rel: 'link, [role=link]',
    Group.prevnext: 'a, button, [role=button]',
}

FILTERS = {
    Group.links: (lambda e: e.hasAttribute('href') and
                  QUrl(e.attribute('href')).scheme() != 'javascript'),
}


def is_visible(elem, mainframe):
    """Check whether the element is currently visible on the screen.

    Args:
        elem: The QWebElement to check.
        mainframe: The main QWebFrame.

    Return:
        True if the element is visible, False otherwise.
    """
    # CSS attributes which hide an element
    hidden_attributes = {
        'visibility': 'hidden',
        'display': 'none',
    }
    if elem.isNull():
        raise ValueError("Element is a null-element!")
    for k, v in hidden_attributes.items():
        if elem.styleProperty(k, QWebElement.ComputedStyle) == v:
            return False
    if (not elem.geometry().isValid()) and elem.geometry().x() == 0:
        # Most likely an invisible link
        return False
    # First check if the element is visible on screen
    elem_rect = rect_on_view(elem)
    if elem_rect.isValid():
        visible_on_screen = mainframe.geometry().intersects(elem_rect)
    else:
        # We got an invalid rectangle (width/height 0/0 probably), but this can
        # still be a valid link.
        visible_on_screen = mainframe.geometry().contains(elem_rect.topLeft())
    # Then check if it's visible in its frame if it's not in the main frame.
    elem_frame = elem.webFrame()
    elem_rect = elem.geometry()
    framegeom = QRect(elem_frame.geometry())
    if not framegeom.isValid():
        visible_in_frame = False
    elif elem_frame.parentFrame() is not None:
        framegeom.moveTo(0, 0)
        framegeom.translate(elem_frame.scrollPosition())
        if elem_rect.isValid():
            visible_in_frame = framegeom.intersects(elem_rect)
        else:
            # We got an invalid rectangle (width/height 0/0 probably), but this
            # can still be a valid link.
            visible_in_frame = framegeom.contains(elem_rect.topLeft())
    else:
        visible_in_frame = visible_on_screen
    return all([visible_on_screen, visible_in_frame])


def rect_on_view(elem):
    """Get the geometry of the element relative to the webview."""
    frame = elem.webFrame()
    rect = QRect(elem.geometry())
    while frame is not None:
        rect.translate(frame.geometry().topLeft())
        rect.translate(frame.scrollPosition() * -1)
        frame = frame.parentFrame()
    return rect


def is_writable(elem):
    """Check wheter an element is writable.

    Args:
        elem: The QWebElement to check.
    """
    return not (elem.hasAttribute('disabled') or elem.hasAttribute('readonly'))


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
    )
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


def is_editable(elem):
    """Check whether we should switch to insert mode for this element.

    FIXME: add tests

    Args:
        elem: The QWebElement to check.

    Return:
        True if we should switch to insert mode, False otherwise.
    """
    # Beginnings of div-classes which are actually some kind of editor.
    div_classes = ['CodeMirror',  # Javascript editor over a textarea
                   'kix-']        # Google Docs editor
    tag = elem.tagName().lower()
    if tag == 'input':
        objtype = elem.attribute('type')
        if objtype in ['text', 'email', 'url', 'tel', 'number', 'password',
                       'search', '']:
            return is_writable(elem)
    elif tag == 'textarea':
        return is_writable(elem)
    elif tag in ('embed', 'applet', 'select'):
        # Flash/Java/...
        return config.get('input', 'insert-mode-on-plugins')
    elif tag == 'object':
        # Could be Flash/Java/..., could be image/audio/...
        if not elem.hasAttribute('type'):
            log.webview.debug("<object> without type clicked...")
            return False
        objtype = elem.attribute('type')
        if (objtype.startswith('application/') or
                elem.hasAttribute('classid')):
            # Let's hope flash/java stuff has an application/* mimetype OR
            # at least a classid attribute. Oh, and let's hope images/...
            # DON'T have a classid attribute. HTML sucks.
            log.webview.debug("<object type='{}'> clicked.".format(objtype))
            return config.get('input', 'insert-mode-on-plugins')
    elif tag == 'div':
        log.webview.debug("div with classes {} clicked!".format(
            elem.classes()))
        for klass in elem.classes():
            if any([klass.startswith(e) for e in div_classes]):
                return True
    elif tag == 'span':
        log.webview.debug("span with classes {} clicked!".format(
            elem.classes()))
    return False
