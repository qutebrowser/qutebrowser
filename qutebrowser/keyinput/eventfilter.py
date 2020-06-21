# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Global Qt event filter which dispatches key events."""

import typing

from PyQt5.QtCore import pyqtSlot, QObject, QEvent
from PyQt5.QtGui import QKeyEvent, QWindow
from PyQt5.QtWidgets import QApplication

from qutebrowser.keyinput import modeman
from qutebrowser.misc import quitter
from qutebrowser.utils import objreg


class EventFilter(QObject):

    """Global Qt event filter.

    Attributes:
        _activated: Whether the EventFilter is currently active.
        _handlers; A {QEvent.Type: callable} dict with the handlers for an
                   event.
    """

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self._activated = True
        self._handlers = {
            QEvent.KeyPress: self._handle_key_event,
            QEvent.KeyRelease: self._handle_key_event,
            QEvent.ShortcutOverride: self._handle_key_event,
        }

    def install(self) -> None:
        QApplication.instance().installEventFilter(self)

    @pyqtSlot()
    def shutdown(self) -> None:
        QApplication.instance().removeEventFilter(self)

    def _handle_key_event(self, event: QKeyEvent) -> bool:
        """Handle a key press/release event.

        Args:
            event: The QEvent which is about to be delivered.

        Return:
            True if the event should be filtered, False if it's passed through.
        """
        active_window = QApplication.instance().activeWindow()
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
        if not isinstance(obj, QWindow):
            # We already handled this same event at some point earlier, so
            # we're not interested in it anymore.
            return False

        typ = event.type()

        if typ not in self._handlers:
            return False

        if not self._activated:
            return False

        handler = self._handlers[typ]
        try:
            return handler(typing.cast(QKeyEvent, event))
        except:
            # If there is an exception in here and we leave the eventfilter
            # activated, we'll get an infinite loop and a stack overflow.
            self._activated = False
            raise


def init() -> None:
    """Initialize the global EventFilter instance."""
    event_filter = EventFilter(parent=QApplication.instance())
    event_filter.install()
    quitter.instance.shutting_down.connect(event_filter.shutdown)
