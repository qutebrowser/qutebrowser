# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


from typing import Dict, List

from PyQt5.QtCore import QObject, QVariant, pyqtSlot
from PyQt5.QtDBus import QDBusConnection, QDBusArgument, QDBusMessage
import pytest

from qutebrowser.utils import utils
from tests.helpers import testutils


class TestNotificationServer(QObject):
    """A libnotify notification server used for testing."""

    # These are the same as in DBusNotificationPresenter. We don't import that
    # because it relies on Qt 5.13, and this fixture is *always* instantiated.
    SERVICE = "org.freedesktop.Notifications"
    TEST_SERVICE = "org.qutebrowser.TestNotifications"
    PATH = "/org/freedesktop/Notifications"
    INTERFACE = "org.freedesktop.Notifications"

    def __init__(self, service: str):
        """Constructs a new server.

        This is safe even if there is no DBus daemon; we don't check whether
        the connection is successful until register().
        """
        # Note that external users should call get() instead.
        super().__init__()
        self._service = service
        # Trying to connect to the bus doesn't fail if there's no bus.
        self._bus = QDBusConnection.sessionBus()
        self._message_id = 0
        # A dict mapping notification IDs to currently-displayed notifications.
        self.messages: Dict[int, QDBusMessage] = {}
        self.supports_body_markup = True

    def register(self) -> bool:
        """Try to register to DBus.

        If no bus is available, returns False.
        If a bus is available but registering fails, raises an AssertionError.
        If registering succeeded, returns True.
        """
        if not self._bus.isConnected():
            return False
        assert self._bus.registerService(self._service)
        assert self._bus.registerObject(TestNotificationServer.PATH,
                                        TestNotificationServer.INTERFACE,
                                        self,
                                        QDBusConnection.ExportAllSlots)
        return True

    def unregister(self) -> None:
        self._bus.unregisterObject(TestNotificationServer.PATH)
        assert self._bus.unregisterService(self._service)

    @pyqtSlot(QDBusMessage, result="uint")
    def Notify(self, message: QDBusMessage) -> QDBusArgument:  # pylint: disable=invalid-name
        self._message_id += 1
        args = message.arguments()
        self.messages[self._message_id] = {
            "title": args[3],
            "body": args[4]
        }
        return self._message_id

    @pyqtSlot(QDBusMessage, result="QStringList")
    def GetCapabilities(self, message: QDBusMessage) -> List[str]:  # pylint: disable=invalid-name
        return ["body-markup"] if self.supports_body_markup else []

    def close(self, notification_id: int) -> None:
        """Sends a close notification for the given ID."""
        message = QDBusMessage.createSignal(
            TestNotificationServer.PATH,
            TestNotificationServer.INTERFACE,
            "NotificationClosed")
        # the 2 here is the notification removal reason; it's effectively
        # arbitrary
        message.setArguments([_as_uint32(notification_id), _as_uint32(2)])
        if not self._bus.send(message):
            raise OSError("Could not send close notification")


@pytest.fixture
def notification_server(qapp):
    server = TestNotificationServer(TestNotificationServer.TEST_SERVICE)
    registered = server.register()
    if not registered:
        assert not (utils.is_linux and testutils.ON_CI), "Expected DBus on Linux CI"
        pytest.skip("No DBus server available")

    yield server
    server.unregister()


def _as_uint32(x: int) -> QVariant:
    variant = QVariant(x)
    assert variant.convert(QVariant.UInt)
    return variant
