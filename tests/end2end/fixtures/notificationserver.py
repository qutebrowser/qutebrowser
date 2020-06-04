# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

import typing

from qutebrowser.browser.webengine.notification import DBusNotificationPresenter

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, QVariant, pyqtSlot
from PyQt5.QtDBus import QDBusConnection, QDBusInterface, QDBus, QDBusArgument, QDBusMessage
import pytest

class TestNotificationServer(QObject):
    """A notification server used for testing.

    This is a singleton, since it doesn't make sense to have multiples of this.
    Users should call `get()` to get the singleton.
    """

    _instance: typing.Optional["TestNotifyServer"] = None

    def __init__(self, service: str):
        # Note that external users should call get() instead.
        super().__init__()
        self._service = service
        self._bus = QDBusConnection.sessionBus()
        assert self._bus.isConnected()
        self._message_id = 0
        # A dict mapping notification IDs to currently-displayed notifications.
        self.messages = {}  # type: typing.Dict[int, QDBusMessage]

    def register(self) -> None:
        assert self._bus.registerService(self._service)
        assert self._bus.registerObject(DBusNotificationPresenter.PATH,
                            DBusNotificationPresenter.INTERFACE,
                            self,
                            QDBusConnection.ExportAllSlots)

    def unregister(self) -> None:
        self._bus.unregisterObject(DBusNotificationPresenter.PATH)
        assert self._bus.unregisterService(self._service)

    @pyqtSlot(QDBusMessage, result="uint")
    def Notify(self, message: QDBusMessage) -> QDBusArgument:
        self._message_id += 1
        self.messages[self._message_id] = message
        return self._message_id

    def close(self, notification_id: int) -> None:
        """Sends a close notification for the given ID."""
        message = QDBusMessage.createSignal(
            DBusNotificationPresenter.PATH,
            DBusNotificationPresenter.INTERFACE,
            "NotificationClosed")
        # the 2 here is the notification removal reason; it's effectively
        # arbitrary
        message.setArguments([_as_uint32(notification_id), _as_uint32(2)])
        if not self._bus.send(message):
            raise IOError("Could not send close notification")

@pytest.fixture
def notification_server(qapp):
    server = TestNotificationServer(DBusNotificationPresenter.TEST_SERVICE)
    try:
        server.register()
        yield server
    finally:
        server.unregister()


def _as_uint32(x: int) -> QVariant:
    variant = QVariant(x)
    assert variant.convert(QVariant.UInt)
    return variant

