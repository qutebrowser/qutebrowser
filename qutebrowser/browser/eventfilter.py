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

"""Event handling for a browser tab."""

from PyQt5.QtCore import QObject, QEvent, Qt, QTimer

from qutebrowser.config import config
from qutebrowser.utils import message, log, usertypes, qtutils, objreg
from qutebrowser.misc import objects
from qutebrowser.keyinput import modeman


class ChildEventFilter(QObject):

    """An event filter re-adding TabEventFilter on ChildEvent.

    This is needed because QtWebEngine likes to randomly change its
    focusProxy...

    FIXME:qtwebengine Add a test for this happening

    Attributes:
        _filter: The event filter to install.
        _widget: The widget expected to send out childEvents.
    """

    def __init__(self, eventfilter, widget, win_id, parent=None):
        super().__init__(parent)
        self._filter = eventfilter
        assert widget is not None
        self._widget = widget
        self._win_id = win_id

    def eventFilter(self, obj, event):
        """Act on ChildAdded events."""
        if event.type() == QEvent.ChildAdded:
            child = event.child()
            log.misc.debug("{} got new child {}, installing filter".format(
                obj, child))
            assert obj is self._widget
            child.installEventFilter(self._filter)

            if qtutils.version_check('5.11', compiled=False, exact=True):
                # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-68076
                pass_modes = [usertypes.KeyMode.command,
                              usertypes.KeyMode.prompt,
                              usertypes.KeyMode.yesno]
                if modeman.instance(self._win_id).mode not in pass_modes:
                    tabbed_browser = objreg.get('tabbed-browser',
                                                scope='window',
                                                window=self._win_id)
                    current_index = tabbed_browser.widget.currentIndex()
                    try:
                        widget_index = tabbed_browser.widget.indexOf(
                            self._widget.parent())
                    except RuntimeError:
                        widget_index = -1
                    if current_index == widget_index:
                        QTimer.singleShot(0, self._widget.setFocus)

        elif event.type() == QEvent.ChildRemoved:
            child = event.child()
            log.misc.debug("{}: removed child {}".format(obj, child))

        return False


class TabEventFilter(QObject):

    """Handle mouse/keyboard events on a tab.

    Attributes:
        _tab: The browsertab object this filter is installed on.
        _handlers: A dict of handler functions for the handled events.
        _ignore_wheel_event: Whether to ignore the next wheelEvent.
        _check_insertmode_on_release: Whether an insertmode check should be
                                      done when the mouse is released.
    """

    def __init__(self, tab, *, parent=None):
        super().__init__(parent)
        self._tab = tab
        self._handlers = {
            QEvent.MouseButtonPress: self._handle_mouse_press,
            QEvent.MouseButtonRelease: self._handle_mouse_release,
            QEvent.Wheel: self._handle_wheel,
            QEvent.ContextMenu: self._handle_context_menu,
            QEvent.KeyRelease: self._handle_key_release,
        }
        self._ignore_wheel_event = False
        self._check_insertmode_on_release = False

    def _handle_mouse_press(self, e):
        """Handle pressing of a mouse button.

        Args:
            e: The QMouseEvent.

        Return:
            True if the event should be filtered, False otherwise.
        """
        is_rocker_gesture = (config.val.input.rocker_gestures and
                             e.buttons() == Qt.LeftButton | Qt.RightButton)

        if e.button() in [Qt.XButton1, Qt.XButton2] or is_rocker_gesture:
            self._mousepress_backforward(e)
            return True

        self._ignore_wheel_event = True

        pos = e.pos()
        if pos.x() < 0 or pos.y() < 0:
            log.mouse.warning("Ignoring invalid click at {}".format(pos))
            return False

        if e.button() != Qt.NoButton:
            self._tab.elements.find_at_pos(pos, self._mousepress_insertmode_cb)

        return False

    def _handle_mouse_release(self, _e):
        """Handle releasing of a mouse button.

        Args:
            e: The QMouseEvent.

        Return:
            True if the event should be filtered, False otherwise.
        """
        # We want to make sure we check the focus element after the WebView is
        # updated completely.
        QTimer.singleShot(0, self._mouserelease_insertmode)
        return False

    def _handle_wheel(self, e):
        """Zoom on Ctrl-Mousewheel.

        Args:
            e: The QWheelEvent.

        Return:
            True if the event should be filtered, False otherwise.
        """
        if self._ignore_wheel_event:
            # See https://github.com/qutebrowser/qutebrowser/issues/395
            self._ignore_wheel_event = False
            return True

        # Don't allow scrolling while hinting
        mode = modeman.instance(self._tab.win_id).mode
        if mode == usertypes.KeyMode.hint:
            return True

        elif e.modifiers() & Qt.ControlModifier:
            if mode == usertypes.KeyMode.passthrough:
                return False

            divider = config.val.zoom.mouse_divider
            if divider == 0:
                # Disable mouse zooming
                return True

            factor = self._tab.zoom.factor() + (e.angleDelta().y() / divider)
            if factor < 0:
                return True

            perc = int(100 * factor)
            message.info("Zoom level: {}%".format(perc), replace=True)
            self._tab.zoom.set_factor(factor)
            return True
        elif (e.modifiers() & Qt.ShiftModifier and
              not qtutils.version_check('5.9', compiled=False)):
            if e.angleDelta().y() > 0:
                self._tab.scroller.left()
            else:
                self._tab.scroller.right()
            return True

        return False

    def _handle_context_menu(self, _e):
        """Suppress context menus if rocker gestures are turned on.

        Args:
            e: The QContextMenuEvent.

        Return:
            True if the event should be filtered, False otherwise.
        """
        return config.val.input.rocker_gestures

    def _handle_key_release(self, e):
        """Ignore repeated key release events going to the website.

        WORKAROUND for https://bugreports.qt.io/browse/QTBUG-77208

        Args:
            e: The QKeyEvent.

        Return:
            True if the event should be filtered, False otherwise.
        """
        return (e.isAutoRepeat() and
                qtutils.version_check('5.10', compiled=False) and
                not qtutils.version_check('5.14', compiled=False) and
                objects.backend == usertypes.Backend.QtWebEngine)

    def _mousepress_insertmode_cb(self, elem):
        """Check if the clicked element is editable."""
        if elem is None:
            # Something didn't work out, let's find the focus element after
            # a mouse release.
            log.mouse.debug("Got None element, scheduling check on "
                            "mouse release")
            self._check_insertmode_on_release = True
            return

        if elem.is_editable():
            log.mouse.debug("Clicked editable element!")
            if config.val.input.insert_mode.auto_enter:
                modeman.enter(self._tab.win_id, usertypes.KeyMode.insert,
                              'click', only_if_normal=True)
        else:
            log.mouse.debug("Clicked non-editable element!")
            if config.val.input.insert_mode.auto_leave:
                modeman.leave(self._tab.win_id, usertypes.KeyMode.insert,
                              'click', maybe=True)

    def _mouserelease_insertmode(self):
        """If we have an insertmode check scheduled, handle it."""
        if not self._check_insertmode_on_release:
            return
        self._check_insertmode_on_release = False

        def mouserelease_insertmode_cb(elem):
            """Callback which gets called from JS."""
            if elem is None:
                log.mouse.debug("Element vanished!")
                return

            if elem.is_editable():
                log.mouse.debug("Clicked editable element (delayed)!")
                modeman.enter(self._tab.win_id, usertypes.KeyMode.insert,
                              'click-delayed', only_if_normal=True)
            else:
                log.mouse.debug("Clicked non-editable element (delayed)!")
                if config.val.input.insert_mode.auto_leave:
                    modeman.leave(self._tab.win_id, usertypes.KeyMode.insert,
                                  'click-delayed', maybe=True)

        self._tab.elements.find_focused(mouserelease_insertmode_cb)

    def _mousepress_backforward(self, e):
        """Handle back/forward mouse button presses.

        Args:
            e: The QMouseEvent.

        Return:
            True if the event should be filtered, False otherwise.
        """
        if e.button() in [Qt.XButton1, Qt.LeftButton]:
            # Back button on mice which have it, or rocker gesture
            if self._tab.history.can_go_back():
                self._tab.history.back()
            else:
                message.error("At beginning of history.")
        elif e.button() in [Qt.XButton2, Qt.RightButton]:
            # Forward button on mice which have it, or rocker gesture
            if self._tab.history.can_go_forward():
                self._tab.history.forward()
            else:
                message.error("At end of history.")

    def eventFilter(self, obj, event):
        """Filter events going to a QWeb(Engine)View.

        Return:
            True if the event should be filtered, False otherwise.
        """
        evtype = event.type()
        if evtype not in self._handlers:
            return False
        if obj is not self._tab.private_api.event_target():
            log.mouse.debug("Ignoring {} to {}".format(
                event.__class__.__name__, obj))
            return False
        return self._handlers[evtype](event)
