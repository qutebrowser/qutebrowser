# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Global Qt event filter which dispatches key events."""

from typing import cast, Optional

from qutebrowser.qt.core import pyqtSlot, QObject, QEvent, qVersion, Qt, QTimer
from qutebrowser.qt.gui import QKeyEvent, QWindow, QInputMethodQueryEvent
from qutebrowser.qt.widgets import QApplication

from qutebrowser.config import config
from qutebrowser.keyinput import modeman
from qutebrowser.misc import quitter, objects
from qutebrowser.utils import objreg, debug, log, qtutils, usertypes


class EventFilter(QObject):

    """Global Qt event filter.

    Attributes:, usertypes
        _activated: Whether the EventFilter is currently active.
        _handlers: A {QEvent.Type: callable} dict with the handlers for an
                   event.
    """

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self._activated = True
        self._handlers = {
            QEvent.Type.KeyPress: self._handle_key_event,
            QEvent.Type.KeyRelease: self._handle_key_event,
            QEvent.Type.ShortcutOverride: self._handle_key_event,
        }
        self._log_qt_events = "log-qt-events" in objects.debug_flags

    def install(self) -> None:
        objects.qapp.installEventFilter(self)

    @pyqtSlot()
    def shutdown(self) -> None:
        objects.qapp.removeEventFilter(self)

    def _handle_key_event(self, event: QKeyEvent) -> bool:
        """Handle a key press/release event.

        Args:
            event: The QEvent which is about to be delivered.

        Return:
            True if the event should be filtered, False if it's passed through.
        """
        active_window = objects.qapp.activeWindow()
        if active_window not in objreg.window_registry.values():
            # Some other window (print dialog, etc.) is focused so we pass the
            # event through.
            return False
        try:
            man = modeman.instance('current')
            return man.handle_event(event)
        except objreg.RegistryUnavailableError:
            # No window available yet, or not a MainWindow
            return False

    def eventFilter(self, obj: Optional[QObject], event: Optional[QEvent]) -> bool:
        """Handle an event.

        Args:
            obj: The object which will get the event.
            event: The QEvent which is about to be delivered.

        Return:
            True if the event should be filtered, False if it's passed through.
        """
        assert event is not None
        ev_type = event.type()

        if self._log_qt_events:
            try:
                source = repr(obj)
            except AttributeError:  # might not be fully initialized yet
                source = type(obj).__name__

            ev_type_str = debug.qenum_key(QEvent, ev_type)
            log.misc.debug(f"{source} got event: {ev_type_str}")

        if (
            ev_type == QEvent.Type.DragEnter and
            qtutils.is_wayland() and
            qVersion() == "6.5.2"
        ):
            # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-115757
            # Fixed in Qt 6.5.3
            # Can't do this via self._handlers since handling it for QWindow
            # seems to be too late.
            log.mouse.warning("Ignoring drag event to prevent Qt crash")
            event.ignore()
            return True

        if not isinstance(obj, QWindow):
            # We already handled this same event at some point earlier, so
            # we're not interested in it anymore.
            return False

        if ev_type not in self._handlers:
            return False

        if not self._activated:
            return False

        handler = self._handlers[ev_type]
        try:
            return handler(cast(QKeyEvent, event))
        except:
            # If there is an exception in here and we leave the eventfilter
            # activated, we'll get an infinite loop and a stack overflow.
            self._activated = False
            raise

""" Handles the cursorRectangleChanged event from the inputMethod

    This provides better input detection
"""
class IMEEventHandler(QObject):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._input_method = QApplication.inputMethod()
        print("adding ime handler")
        self._input_method.cursorRectangleChanged.connect(
            self.cursor_rectangle_changed
        )
        self._last_seen_rect = None

    @pyqtSlot()
    def cursor_rectangle_changed(self):
        # todo:
        #   clear last_seen_rect on mode exit so that you can click on
        #     focused input field and re-enter
        #   last seen rect per window? tab? tab might work better with
        #      remembering focus for tabs
        #   anything to unregister? saw some hangs on crash but might be
        #      because of being a temp basedir
        # some input examples here https://www.javatpoint.com/html-form-input-types
        #  <input type="date">: doesn't report as having an input method enabled,
        #  although the existing heuristics pick it up
        # if insert_mode_auto_load is false but there is a blinking cursor on
        # load clicking the scroll bar will enter insert mode

        new_rect = self._input_method.cursorRectangle()
        if self._last_seen_rect and self._last_seen_rect.contains(new_rect):
            print("contains")
            return

        self._last_seen_rect = new_rect

        # implementation detail: qtwebengine doesn't set anchor for input
        # fields in a web page, qt widgets do, I haven't found any cases where
        # it doesn't work yet. Would like to compare with a "get focused thing
        # and examine" check first and compare across versions.
        anchor_rect = self._input_method.anchorRectangle()
        if anchor_rect:
            print("Not handling because anchor rect is set")
            return

        focused_window = objreg.last_focused_window()
        focus_object = QApplication.focusObject()
        query = None

        if not new_rect and focus_object:
            # sometimes we get a rectangle changed event and the queried
            # rectangle is empty but we are still in an editable element. For
            # instance when pressing enter in a text box on confluence or jira
            # (including comment on the Qt instance) and tabbing between cells
            # on https://html-online.com/editor/
            # Checking ImEnabled helps in these cases.
            query = QInputMethodQueryEvent(Qt.InputMethodQuery.ImEnabled)
            QApplication.sendEvent(focus_object, query)

        if new_rect or (query and query.value(Qt.InputMethodQuery.ImEnabled)):
            log.mouse.debug("Clicked editable element!")
            if config.val.input.insert_mode.auto_enter:
                modeman.enter(focused_window.win_id, usertypes.KeyMode.insert,
                              'click', only_if_normal=True)
        else:
            log.mouse.debug("Clicked non-editable element!")
            if config.val.input.insert_mode.auto_leave:
                modeman.leave(focused_window.win_id, usertypes.KeyMode.insert,
                              'click', maybe=True)


_ime_event_handler_instance = None


def init() -> None:
    """Initialize the global EventFilter instance."""
    event_filter = EventFilter(parent=objects.qapp)
    event_filter.install()
    quitter.instance.shutting_down.connect(event_filter.shutdown)

    def donothing() -> None:
        _ime_event_handler_instance = IMEEventHandler(parent=QApplication.instance())
    QTimer.singleShot(1000, donothing)
