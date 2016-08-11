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

"""Mouse handling for a browser tab."""


from qutebrowser.config import config
from qutebrowser.utils import message, log, usertypes


from PyQt5.QtCore import QObject, QEvent, Qt


class ChildEventFilter(QObject):

    """An event filter re-adding MouseEventFilter on ChildEvent.

    This is needed because QtWebEngine likes to randomly change its
    focusProxy...

    FIXME:qtwebengine Add a test for this happening

    Attributes:
        _filter: The event filter to install.
        _widget: The widget expected to send out childEvents.
    """

    def __init__(self, eventfilter, widget, parent=None):
        super().__init__(parent)
        self._filter = eventfilter
        assert widget is not None
        self._widget = widget

    def eventFilter(self, obj, event):
        """Act on ChildAdded events."""
        if event.type() == QEvent.ChildAdded:
            child = event.child()
            log.mouse.debug("{} got new child {}, installing filter".format(
                obj, child))
            assert obj is self._widget
            child.installEventFilter(self._filter)
        return False


class MouseEventFilter(QObject):

    """Handle mouse events on a tab.

    Attributes:
        _tab: The browsertab object this filter is installed on.
        _handlers: A dict of handler functions for the handled events.
        _ignore_wheel_event: Whether to ignore the next wheelEvent.
    """

    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self._tab = tab
        self._handlers = {
            QEvent.MouseButtonPress: self._handle_mouse_press,
            QEvent.Wheel: self._handle_wheel,
        }
        self._ignore_wheel_event = False

    def _handle_mouse_press(self, _obj, e):
        """Handle pressing of a mouse button."""
        is_rocker_gesture = (config.get('input', 'rocker-gestures') and
                             e.buttons() == Qt.LeftButton | Qt.RightButton)

        if e.button() in [Qt.XButton1, Qt.XButton2] or is_rocker_gesture:
            self._mousepress_backforward(e)
            return True

        self._ignore_wheel_event = True
        self._mousepress_opentarget(e)

        return False

    def _handle_wheel(self, _obj, e):
        """Zoom on Ctrl-Mousewheel.

        Args:
            e: The QWheelEvent.
        """
        if self._ignore_wheel_event:
            # See https://github.com/The-Compiler/qutebrowser/issues/395
            self._ignore_wheel_event = False
            return True

        if e.modifiers() & Qt.ControlModifier:
            divider = config.get('input', 'mouse-zoom-divider')
            factor = self._tab.zoom.factor() + (e.angleDelta().y() / divider)
            if factor < 0:
                return False
            perc = int(100 * factor)
            message.info(self._tab.win_id, "Zoom level: {}%".format(perc))
            self._tab.zoom.set_factor(factor)

        return False

    def _mousepress_backforward(self, e):
        """Handle back/forward mouse button presses.

        Args:
            e: The QMouseEvent.
        """
        if e.button() in [Qt.XButton1, Qt.LeftButton]:
            # Back button on mice which have it, or rocker gesture
            if self._tab.history.can_go_back():
                self._tab.history.back()
            else:
                message.error(self._tab.win_id, "At beginning of history.",
                              immediately=True)
        elif e.button() in [Qt.XButton2, Qt.RightButton]:
            # Forward button on mice which have it, or rocker gesture
            if self._tab.history.can_go_forward():
                self._tab.history.forward()
            else:
                message.error(self._tab.win_id, "At end of history.",
                              immediately=True)

    def _mousepress_opentarget(self, e):
        """Set the open target when something was clicked.

        Args:
            e: The QMouseEvent.
        """
        if e.button() == Qt.MidButton or e.modifiers() & Qt.ControlModifier:
            background_tabs = config.get('tabs', 'background-tabs')
            if e.modifiers() & Qt.ShiftModifier:
                background_tabs = not background_tabs
            if background_tabs:
                target = usertypes.ClickTarget.tab_bg
            else:
                target = usertypes.ClickTarget.tab
            self._tab.data.open_target = target
            log.mouse.debug("Ctrl/Middle click, setting target: {}".format(
                target))
        else:
            self._tab.data.open_target = usertypes.ClickTarget.normal
            log.mouse.debug("Normal click, setting normal target")

    def eventFilter(self, obj, event):
        """Filter events going to a QWeb(Engine)View."""
        evtype = event.type()
        if evtype not in self._handlers:
            return False
        return self._handlers[evtype](obj, event)
