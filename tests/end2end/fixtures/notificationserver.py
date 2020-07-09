# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

import typing

from PyQt5.QtCore import QObject, QVariant, pyqtSlot
from PyQt5.QtDBus import QDBusConnection, QDBusArgument, QDBusMessage
import pytest

from qutebrowser.utils import utils


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
        self.messages = {}  # type: typing.Dict[int, QDBusMessage]

    def register(self) -> None:
        assert self._bus.isConnected()
        assert self._bus.registerService(self._service)
        assert self._bus.registerObject(TestNotificationServer.PATH,
                                        TestNotificationServer.INTERFACE,
                                        self,
                                        QDBusConnection.ExportAllSlots)

    def unregister(self) -> None:
        self._bus.unregisterObject(TestNotificationServer.PATH)
        assert self._bus.unregisterService(self._service)

    @pyqtSlot(QDBusMessage, result="uint")
    def Notify(self, message: QDBusMessage) -> QDBusArgument:  # pylint: disable=invalid-name
        self._message_id += 1
        self.messages[self._message_id] = message
        return self._message_id

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
            raise IOError("Could not send close notification")


@pytest.fixture
def notification_server(qapp):
    server = TestNotificationServer(TestNotificationServer.TEST_SERVICE)
    if utils.is_windows or utils.is_mac:
        yield server
    else:
        try:
            server.register()
            yield server
        finally:
            server.unregister()


def _as_uint32(x: int) -> QVariant:
    variant = QVariant(x)
    assert variant.convert(QVariant.UInt)
    return variant
