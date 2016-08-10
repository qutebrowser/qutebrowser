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
from qutebrowser.utils import message, debug, log


from PyQt5.QtCore import QObject, QEvent, Qt


class ChildEventFilter(QObject):

    """An event filter re-adding MouseEventFilter on ChildEvent.

    This is needed because QtWebEngine likes to randomly change its
    focusProxy...

    FIXME:qtwebengine Add a test for this happening
    """

    def __init__(self, eventfilter, widget, parent=None):
        super().__init__(parent)
        self._filter = eventfilter
        assert widget is not None
        self._widget = widget

    def eventFilter(self, obj, event):
        if event.type() == QEvent.ChildAdded:
            child = event.child()
            log.mouse.debug("{} got new child {}, installing filter".format(
                obj, child))
            assert obj is self._widget
            child.installEventFilter(self._filter)
        return False


class MouseEventFilter(QObject):

    """Handle mouse events on a tab."""

    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self._tab = tab
        self._handlers = {
            QEvent.MouseButtonPress: self._handle_mouse_press,
        }

    def _handle_mouse_press(self, _obj, e):
        """Handle pressing of a mouse button."""
        is_rocker_gesture = (config.get('input', 'rocker-gestures') and
                             e.buttons() == Qt.LeftButton | Qt.RightButton)

        if e.button() in [Qt.XButton1, Qt.XButton2] or is_rocker_gesture:
            self._mousepress_backforward(e)
            return True
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

    def eventFilter(self, obj, event):
        """Filter events going to a QWeb(Engine)View."""
        evtype = event.type()
        if evtype not in self._handlers:
            return False
        return self._handlers[evtype](obj, event)
