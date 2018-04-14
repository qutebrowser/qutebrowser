# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2018 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
"""

import enum
import collections.abc

from PyQt5.QtCore import QUrl, Qt, QEvent, QTimer
from PyQt5.QtGui import QMouseEvent

from qutebrowser.config import config
from qutebrowser.keyinput import modeman
from qutebrowser.mainwindow import mainwindow
from qutebrowser.utils import log, usertypes, utils, qtutils, objreg


Group = enum.Enum('Group', ['all', 'links', 'images', 'url', 'inputs'])


SELECTORS = {
    Group.all: ('a, area, textarea, select, input:not([type=hidden]), button, '
                'frame, iframe, link, summary, [onclick], [onmousedown], '
                '[role=link], [role=option], [role=button], img, '
                # Angular 1 selectors
                '[ng-click], [ngClick], [data-ng-click], [x-ng-click]'),
    Group.links: 'a[href], area[href], link[href], [role=link][href]',
    Group.images: 'img',
    Group.url: '[src], [href]',
    Group.inputs: ('input[type=text], input[type=email], input[type=url], '
                   'input[type=tel], input[type=number], '
                   'input[type=password], input[type=search], '
                   'input:not([type]), textarea'),
}


class Error(Exception):

    """Base class for WebElement errors."""

    pass


class OrphanedError(Error):

    """Raised when a webelement's parent has vanished."""

    pass


class AbstractWebElement(collections.abc.MutableMapping):

    """A wrapper around QtWebKit/QtWebEngine web element.

    Attributes:
        tab: The tab associated with this element.
    """

    def __init__(self, tab):
        self._tab = tab

    def __eq__(self, other):
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError

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
            html = utils.compact_text(self.outer_xml(), 500)
        except Error:
            html = None
        return utils.get_repr(self, html=html)

    def has_frame(self):
        """Check if this element has a valid frame attached."""
        raise NotImplementedError

    def geometry(self):
        """Get the geometry for this element."""
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

    def value(self):
        """Get the value attribute for this element, or None."""
        raise NotImplementedError

    def set_value(self, value):
        """Set the element value."""
        raise NotImplementedError

    def insert_text(self, text):
        """Insert the given text into the element."""
        raise NotImplementedError

    def rect_on_view(self, *, elem_geometry=None, no_js=False):
        """Get the geometry of the element relative to the webview.

        Uses the getClientRects() JavaScript method to obtain the collection of
        rectangles containing the element and returns the first rectangle which
        is large enough (larger than 1px times 1px). If all rectangles returned
        by getClientRects() are too small, falls back to elem.rect_on_view().

        Skipping of small rectangles is due to <a> elements containing other
        elements with "display:block" style, see
        https://github.com/qutebrowser/qutebrowser/issues/1298

        Args:
            elem_geometry: The geometry of the element, or None.
                           Calling QWebElement::geometry is rather expensive so
                           we want to avoid doing it twice.
            no_js: Fall back to the Python implementation
        """
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
            log.webelem.debug("<object> without type clicked...")
            return False
        objtype = self['type'].lower()
        if objtype.startswith('application/') or 'classid' in self:
            # Let's hope flash/java stuff has an application/* mimetype OR
            # at least a classid attribute. Oh, and let's hope images/...
            # DON'T have a classid attribute. HTML sucks.
            log.webelem.debug("<object type='{}'> clicked.".format(objtype))
            return config.val.input.insert_mode.plugins
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

    def _is_editable_classes(self):
        """Check if an element is editable based on its classes.

        Return:
            True if the element is editable, False otherwise.
        """
        # Beginnings of div-classes which are actually some kind of editor.
        classes = {
            'div': ['CodeMirror',  # Javascript editor over a textarea
                    'kix-',  # Google Docs editor
                    'ace_'],  # http://ace.c9.io/
            'pre': ['CodeMirror'],
        }
        relevant_classes = classes[self.tag_name()]
        for klass in self.classes():
            if any(klass.strip().startswith(e) for e in relevant_classes):
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
        log.webelem.debug("Checking if element is editable: {}".format(
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
            return config.val.input.insert_mode.plugins and not strict
        elif tag == 'object':
            return self._is_editable_object() and not strict
        elif tag in ['div', 'pre']:
            return self._is_editable_classes() and not strict
        return False

    def is_text_input(self):
        """Check if this element is some kind of text box."""
        roles = ('combobox', 'textbox')
        tag = self.tag_name()
        return self.get('role', None) in roles or tag in ['input', 'textarea']

    def remove_blank_target(self):
        """Remove target from link."""
        raise NotImplementedError

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

    def is_link(self):
        """Return True if this AbstractWebElement is a link."""
        href_tags = ['a', 'area', 'link']
        return self.tag_name() in href_tags and 'href' in self

    def _mouse_pos(self):
        """Get the position to click/hover."""
        # Click the center of the largest square fitting into the top/left
        # corner of the rectangle, this will help if part of the <a> element
        # is hidden behind other elements
        # https://github.com/qutebrowser/qutebrowser/issues/1005
        rect = self.rect_on_view()
        if rect.width() > rect.height():
            rect.setWidth(rect.height())
        else:
            rect.setHeight(rect.width())
        pos = rect.center()
        if pos.x() < 0 or pos.y() < 0:
            raise Error("Element position is out of view!")
        return pos

    def _move_text_cursor(self):
        """Move cursor to end after clicking."""
        raise NotImplementedError

    def _click_fake_event(self, click_target):
        """Send a fake click event to the element."""
        pos = self._mouse_pos()

        log.webelem.debug("Sending fake click to {!r} at position {} with "
                          "target {}".format(self, pos, click_target))

        modifiers = {
            usertypes.ClickTarget.normal: Qt.NoModifier,
            usertypes.ClickTarget.window: Qt.AltModifier | Qt.ShiftModifier,
            usertypes.ClickTarget.tab: Qt.ControlModifier,
            usertypes.ClickTarget.tab_bg: Qt.ControlModifier,
        }
        if config.val.tabs.background:
            modifiers[usertypes.ClickTarget.tab] |= Qt.ShiftModifier
        else:
            modifiers[usertypes.ClickTarget.tab_bg] |= Qt.ShiftModifier

        events = [
            QMouseEvent(QEvent.MouseMove, pos, Qt.NoButton, Qt.NoButton,
                        Qt.NoModifier),
            QMouseEvent(QEvent.MouseButtonPress, pos, Qt.LeftButton,
                        Qt.LeftButton, modifiers[click_target]),
            QMouseEvent(QEvent.MouseButtonRelease, pos, Qt.LeftButton,
                        Qt.NoButton, modifiers[click_target]),
        ]

        for evt in events:
            self._tab.send_event(evt)

        QTimer.singleShot(0, self._move_text_cursor)

    def _click_editable(self, click_target):
        """Fake a click on an editable input field."""
        raise NotImplementedError

    def _click_js(self, click_target):
        """Fake a click by using the JS .click() method."""
        raise NotImplementedError

    def _click_href(self, click_target):
        """Fake a click on an element with a href by opening the link."""
        baseurl = self._tab.url()
        url = self.resolve_url(baseurl)
        if url is None:
            self._click_fake_event(click_target)
            return

        tabbed_browser = objreg.get('tabbed-browser', scope='window',
                                    window=self._tab.win_id)

        if click_target in [usertypes.ClickTarget.tab,
                            usertypes.ClickTarget.tab_bg]:
            background = click_target == usertypes.ClickTarget.tab_bg
            tabbed_browser.tabopen(url, background=background)
        elif click_target == usertypes.ClickTarget.window:
            window = mainwindow.MainWindow(private=tabbed_browser.private)
            window.show()
            window.tabbed_browser.tabopen(url)
        else:
            raise ValueError("Unknown ClickTarget {}".format(click_target))

    def click(self, click_target, *, force_event=False):
        """Simulate a click on the element.

        Args:
            click_target: A usertypes.ClickTarget member, what kind of click
                          to simulate.
            force_event: Force generating a fake mouse event.
        """
        log.webelem.debug("Clicking {!r} with click_target {}, force_event {}"
                          .format(self, click_target, force_event))

        if force_event:
            self._click_fake_event(click_target)
            return

        if click_target == usertypes.ClickTarget.normal:
            if self.is_link():
                log.webelem.debug("Clicking via JS click()")
                self._click_js(click_target)
            elif self.is_editable(strict=True):
                log.webelem.debug("Clicking via JS focus()")
                self._click_editable(click_target)
                if config.val.input.insert_mode.auto_enter:
                    modeman.enter(self._tab.win_id, usertypes.KeyMode.insert,
                                  'clicking input')
            else:
                self._click_fake_event(click_target)
        elif click_target in [usertypes.ClickTarget.tab,
                              usertypes.ClickTarget.tab_bg,
                              usertypes.ClickTarget.window]:
            if self.is_link():
                self._click_href(click_target)
            else:
                self._click_fake_event(click_target)
        else:
            raise ValueError("Unknown ClickTarget {}".format(click_target))

    def hover(self):
        """Simulate a mouse hover over the element."""
        pos = self._mouse_pos()
        event = QMouseEvent(QEvent.MouseMove, pos, Qt.NoButton, Qt.NoButton,
                            Qt.NoModifier)
        self._tab.send_event(event)
