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
        self.service = service
        self.bus = QDBusConnection.sessionBus()
        self.messages = []  # type: typing.List[QDBusMessage]

    def register(self) -> None:
        assert self.bus.registerService(self.service)
        assert self.registerObject(DBusNotificationPresenter.PATH,
                            DBusNotificationPresenter.INTERFACE,
                            self,
                            QDBusConnection.ExportAllSlots)

    def unregister(self) -> None:
        assert self.bus.unregisterService(self.service)
        self.messages = []

    @pyqtSlot(QDBusMessage)
    def Notify(self, message: QDBusMessage) -> None:
        self.messages.append(message)

    def close(self, notification_id: int) -> None:
        """Sends a close notification for the given ID."""
        message = QDBusMessage.createSignal(
            DBusNotificationPresenter.PATH,
            DBusNotificationPresenter.INTERFACE,
            "NotificationClosed")
        message.setArguments([_as_uint32(notification_id), _as_uint32(2)])
        if not self.bus.send(message):
            raise IOError("Could not send close notification")

@pytest.fixture
def notification_server(qapp):
    server = TestNotificationServer(DBusNotificationPresenter.TEST_SERVICE)
    server.register()
    yield server
    server.unregister()


def _as_uint32(x: int) -> QVariant:
    variant = QVariant(x)
    variant.convert(QVariant.UInt)
    return variant

