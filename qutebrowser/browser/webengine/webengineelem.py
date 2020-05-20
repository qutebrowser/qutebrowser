# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2016-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# pylint: disable=unused-argument

"""QtWebEngine specific part of the web element API."""

import typing

from PyQt5.QtCore import QRect, Qt, QPoint, QEventLoop
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineSettings

from qutebrowser.utils import log, javascript, urlutils, usertypes
from qutebrowser.browser import webelem

if typing.TYPE_CHECKING:
    from qutebrowser.browser.webengine import webenginetab


class WebEngineElement(webelem.AbstractWebElement):

    """A web element for QtWebEngine, using JS under the hood."""

    def __init__(self, js_dict: typing.Dict[str, typing.Any],
                 tab: 'webenginetab.WebEngineTab') -> None:
        super().__init__(tab)
        # Do some sanity checks on the data we get from JS
        js_dict_types = {
            'id': int,
            'text': str,
            'value': (str, int, float),
            'tag_name': str,
            'outer_xml': str,
            'class_name': str,
            'rects': list,
            'attributes': dict,
            'caret_position': (int, type(None)),
        }  # type: typing.Dict[str, typing.Union[type, typing.Tuple[type,...]]]
        assert set(js_dict.keys()).issubset(js_dict_types.keys())
        for name, typ in js_dict_types.items():
            if name in js_dict and not isinstance(js_dict[name], typ):
                raise TypeError("Got {} for {} from JS but expected {}: "
                                "{}".format(type(js_dict[name]), name, typ,
                                            js_dict))
        for name, value in js_dict['attributes'].items():
            if not isinstance(name, str):
                raise TypeError("Got {} ({}) for attribute name from JS: "
                                "{}".format(name, type(name), js_dict))
            if not isinstance(value, str):
                raise TypeError("Got {} ({}) for attribute {} from JS: "
                                "{}".format(value, type(value), name, js_dict))
        for rect in js_dict['rects']:
            assert set(rect.keys()) == {'top', 'right', 'bottom', 'left',
                                        'height', 'width'}, rect.keys()
            for value in rect.values():
                if not isinstance(value, (int, float)):
                    raise TypeError("Got {} ({}) for rect from JS: "
                                    "{}".format(value, type(value), js_dict))

        self._id = js_dict['id']
        self._js_dict = js_dict

    def __str__(self) -> str:
        return self._js_dict.get('text', '')

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WebEngineElement):
            return NotImplemented
        return self._id == other._id

    def __getitem__(self, key: str) -> str:
        attrs = self._js_dict['attributes']
        return attrs[key]

    def __setitem__(self, key: str, val: str) -> None:
        self._js_dict['attributes'][key] = val
        self._js_call('set_attribute', key, val)

    def __delitem__(self, key: str) -> None:
        log.stub()

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self._js_dict['attributes'])

    def __len__(self) -> int:
        return len(self._js_dict['attributes'])

    def _js_call(self, name: str, *args: webelem.JsValueType,
                 callback: typing.Callable[[typing.Any], None] = None) -> None:
        """Wrapper to run stuff from webelem.js."""
        if self._tab.is_deleted():
            raise webelem.OrphanedError("Tab containing element vanished")
        js_code = javascript.assemble('webelem', name, self._id, *args)
        self._tab.run_js_async(js_code, callback=callback)

    def has_frame(self) -> bool:
        return True

    def geometry(self) -> QRect:
        log.stub()
        return QRect()

    def classes(self) -> typing.List[str]:
        """Get a list of classes assigned to this element."""
        return self._js_dict['class_name'].split()

    def tag_name(self) -> str:
        """Get the tag name of this element.

        The returned name will always be lower-case.
        """
        tag = self._js_dict['tag_name']
        assert isinstance(tag, str), tag
        return tag.lower()

    def outer_xml(self) -> str:
        """Get the full HTML representation of this element."""
        return self._js_dict['outer_xml']

    def value(self) -> webelem.JsValueType:
        return self._js_dict.get('value', None)

    def set_value(self, value: webelem.JsValueType) -> None:
        self._js_call('set_value', value)

    def dispatch_event(self, event: str,
                       bubbles: bool = False,
                       cancelable: bool = False,
                       composed: bool = False) -> None:
        self._js_call('dispatch_event', event, bubbles, cancelable, composed)

    def caret_position(self) -> typing.Optional[int]:
        """Get the text caret position for the current element.

        If the element is not a text element, None is returned.
        """
        return self._js_dict.get('caret_position', None)

    def insert_text(self, text: str) -> None:
        if not self.is_editable(strict=True):
            raise webelem.Error("Element is not editable!")
        log.webelem.debug("Inserting text into element {!r}".format(self))
        self._js_call('insert_text', text)

    def rect_on_view(self, *, elem_geometry: QRect = None,
                     no_js: bool = False) -> QRect:
        """Get the geometry of the element relative to the webview.

        Skipping of small rectangles is due to <a> elements containing other
        elements with "display:block" style, see
        https://github.com/qutebrowser/qutebrowser/issues/1298

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
                # We're not checking for zoom.text_only here as that doesn't
                # exist for QtWebEngine.
                zoom = self._tab.zoom.factor()
                rect = QRect(int(left * zoom), int(top * zoom),
                             int(width * zoom), int(height * zoom))
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

    def remove_blank_target(self) -> None:
        if self._js_dict['attributes'].get('target') == '_blank':
            self._js_dict['attributes']['target'] = '_top'
        self._js_call('remove_blank_target')

    def delete(self) -> None:
        self._js_call('delete')

    def _move_text_cursor(self) -> None:
        if self.is_text_input() and self.is_editable():
            self._js_call('move_cursor_to_end')

    def _requires_user_interaction(self) -> bool:
        baseurl = self._tab.url()
        url = self.resolve_url(baseurl)
        if url is None:
            return True
        if baseurl.scheme() == url.scheme():  # e.g. a qute:// link
            return False
        return url.scheme() not in urlutils.WEBENGINE_SCHEMES

    def _click_editable(self, click_target: usertypes.ClickTarget) -> None:
        # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-58515
        ev = QMouseEvent(QMouseEvent.MouseButtonPress, QPoint(0, 0),
                         QPoint(0, 0), QPoint(0, 0), Qt.NoButton, Qt.NoButton,
                         Qt.NoModifier, Qt.MouseEventSynthesizedBySystem)
        self._tab.send_event(ev)
        # This actually "clicks" the element by calling focus() on it in JS.
        self._js_call('focus')
        self._move_text_cursor()

    def _click_js(self, _click_target: usertypes.ClickTarget) -> None:
        # FIXME:qtwebengine Have a proper API for this
        # pylint: disable=protected-access
        view = self._tab._widget
        assert view is not None
        # pylint: enable=protected-access
        attribute = QWebEngineSettings.JavascriptCanOpenWindows
        could_open_windows = view.settings().testAttribute(attribute)
        view.settings().setAttribute(attribute, True)

        # Get QtWebEngine do apply the settings
        # (it does so with a 0ms QTimer...)
        # This is also used in Qt's tests:
        # https://github.com/qt/qtwebengine/commit/5e572e88efa7ba7c2b9138ec19e606d3e345ac90
        QApplication.processEvents(  # type: ignore[call-overload]
            QEventLoop.ExcludeSocketNotifiers |
            QEventLoop.ExcludeUserInputEvents)

        def reset_setting(_arg: typing.Any) -> None:
            """Set the JavascriptCanOpenWindows setting to its old value."""
            assert view is not None
            try:
                view.settings().setAttribute(attribute, could_open_windows)
            except RuntimeError:
                # Happens if this callback gets called during QWebEnginePage
                # destruction, i.e. if the tab was closed in the meantime.
                pass

        self._js_call('click', callback=reset_setting)
