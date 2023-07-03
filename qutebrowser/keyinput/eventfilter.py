# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Global Qt event filter which dispatches key events."""

from typing import cast

from qutebrowser.qt import machinery
from qutebrowser.qt.core import pyqtSlot, QObject, QEvent
from qutebrowser.qt.gui import QKeyEvent, QWindow

from qutebrowser.keyinput import modeman
from qutebrowser.misc import quitter, objects
from qutebrowser.utils import objreg, debug, log


class EventFilter(QObject):

    """Global Qt event filter.

    Attributes:
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

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Handle an event.

        Args:
            obj: The object which will get the event.
            event: The QEvent which is about to be delivered.

        Return:
            True if the event should be filtered, False if it's passed through.
        """
        ev_type = event.type()
        if machinery.IS_QT6:
            ev_type = cast(QEvent.Type, ev_type)

        if self._log_qt_events:
            try:
                source = repr(obj)
            except AttributeError:  # might not be fully initialized yet
                source = type(obj).__name__

            ev_type_str = debug.qenum_key(QEvent, ev_type)
            log.misc.debug(f"{source} got event: {ev_type_str}")

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


def init() -> None:
    """Initialize the global EventFilter instance."""
    event_filter = EventFilter(parent=objects.qapp)
    event_filter.install()
    quitter.instance.shutting_down.connect(event_filter.shutdown)
