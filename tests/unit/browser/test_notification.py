# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2022 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Unit tests for notification support."""

from typing import List, Dict, Any, Optional

import pytest
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QImage
from PyQt5.QtDBus import QDBusMessage, QDBus, QDBusConnection

from qutebrowser.misc import objects
from qutebrowser.browser.webengine import notification


pytestmark = [pytest.mark.qtwebengine_notifications]
dbus_test = pytest.mark.linux


class FakeDBusMessage:

    def __init__(
        self,
        signature: str,
        *arguments: Any,
        typ: QDBusMessage.MessageType = QDBusMessage.MessageType.ReplyMessage,
        error_name: Optional[str] = None,
    ) -> None:
        self._signature = signature
        self._arguments = arguments
        self._type = typ
        self._error_name = error_name

    def arguments(self) -> List[Any]:
        return self._arguments

    def signature(self) -> str:
        return self._signature

    def type(self) -> QDBusMessage.MessageType:
        return self._type

    def errorName(self) -> str:
        assert self._error_name is not None
        return self._error_name

    def errorMessage(self):
        assert self._error_name is not None
        return f"error: {self._error_name}"

    @classmethod
    def create_error(cls, error_name: str) -> "FakeDBusMessage":
        return cls(
            "s",
            f"error argument: {error_name}",
            typ=QDBusMessage.MessageType.ErrorMessage,
            error_name=error_name,
        )


class FakeDBusInterface:

    CAPABILITIES_REPLY = FakeDBusMessage("as", ["actions"])

    def __init__(
        self,
        service: str,
        path: str,
        interface: str,
        bus: QDBusConnection,
    ) -> None:
        assert service.startswith(notification.DBusNotificationAdapter.TEST_SERVICE)
        assert path == notification.DBusNotificationAdapter.PATH
        assert interface == notification.DBusNotificationAdapter.INTERFACE

        self.notify_reply = None

    def isValid(self) -> bool:
        return True

    def call(self, mode: QDBus.CallMode, method: str, *args: Any) -> FakeDBusMessage:
        meth = getattr(self, f"_call_{method}")
        return meth(*args)

    def _call_GetCapabilities(self) -> FakeDBusMessage:
        return self.CAPABILITIES_REPLY

    def _call_Notify(
        self,
        appname: str,
        replaces_id: int,
        icon: str,
        title: str,
        body: str,
        actions: List[str],
        hints: Dict[str, Any],
        timeout: int,
    ) -> FakeDBusMessage:
        assert self.notify_reply is not None
        return self.notify_reply


class FakeWebEngineNotification:

    def origin(self) -> QUrl:
        return QUrl("https://example.org")

    def icon(self) -> QImage:
        return QImage()

    def title(self) -> str:
        return "notification title"

    def message(self) -> str:
        return "notification message"


@pytest.fixture
def dbus_adapter_patches(monkeypatch, config_stub):
    monkeypatch.setattr(objects, "debug_flags", ["test-notification-service"])
    monkeypatch.setattr(notification, "QDBusInterface", FakeDBusInterface)


@pytest.fixture
def dbus_adapter(dbus_adapter_patches):
    return notification.DBusNotificationAdapter()


@pytest.fixture
def fake_notification():
    return FakeWebEngineNotification()


@dbus_test
class TestDBus:

    def test_notify_fatal_error(self, dbus_adapter, fake_notification):
        dbus_adapter.interface.notify_reply = FakeDBusMessage.create_error("test")
        with pytest.raises(notification.DBusError):
            dbus_adapter.present(fake_notification, replaces_id=None)

    def test_notify_non_fatal_error(self, qtbot, dbus_adapter, fake_notification):
        error = "org.freedesktop.DBus.Error.NoReply"
        dbus_adapter.interface.notify_reply = FakeDBusMessage.create_error(error)
        with qtbot.wait_signal(dbus_adapter.error) as blocker:
            dbus_adapter.present(fake_notification, replaces_id=None)
        assert blocker.args == [f"error: {error}"]

    def test_capabilities_error(self, qtbot, dbus_adapter_patches, monkeypatch):
        error = "org.freedesktop.DBus.Error.NoReply"
        monkeypatch.setattr(
            FakeDBusInterface,
            "CAPABILITIES_REPLY",
            FakeDBusMessage.create_error(error),
        )
        with pytest.raises(notification.DBusError):
            notification.DBusNotificationAdapter()
