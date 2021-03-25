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

import dataclasses
import itertools
from typing import Dict, List

from PyQt5.QtCore import QObject, QVariant, pyqtSlot
from PyQt5.QtDBus import QDBusConnection, QDBusArgument, QDBusMessage
import pytest

from qutebrowser.browser.webengine import notification
from qutebrowser.utils import utils
from tests.helpers import testutils


@dataclasses.dataclass
class NotificationProperties:

    title: str
    body: str
    replaces_id: int


def _as_uint32(x: int) -> QVariant:
    variant = QVariant(x)
    assert variant.convert(QVariant.UInt)
    return variant


class TestNotificationServer(QObject):
    """A libnotify notification server used for testing."""

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
        self._message_id_gen = itertools.count(1)
        # A dict mapping notification IDs to currently-displayed notifications.
        self.messages: Dict[int, NotificationProperties] = {}
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
        assert self._bus.registerObject(
            notification.DBusNotificationPresenter.PATH,
            notification.DBusNotificationPresenter.INTERFACE,
            self,
            QDBusConnection.ExportAllSlots,
        )
        return True

    def unregister(self) -> None:
        self._bus.unregisterObject(notification.DBusNotificationPresenter.PATH)
        assert self._bus.unregisterService(self._service)

    def _parse_notify_args(self, appname, replaces_id, icon, title, body, actions,
                           hints, timeout) -> NotificationProperties:
        """Parse a Notify dbus reply.

        Checks all constant values and returns a NotificationProperties object for
        values being checked inside test cases.
        """
        assert appname == "qutebrowser"
        assert icon == "qutebrowser"
        assert actions == ['default', '']
        assert timeout == -1

        assert hints.keys() == {'x-qutebrowser-origin', "desktop-entry"}
        assert hints['x-qutebrowser-origin'].startswith('http://localhost:')
        assert hints['desktop-entry'] == 'org.qutebrowser.qutebrowser'

        if replaces_id != 0:
            assert replaces_id in self.messages

        return NotificationProperties(title=title, body=body, replaces_id=replaces_id)

    def close(self, notification_id: int) -> None:
        """Sends a close notification for the given ID."""
        message = QDBusMessage.createSignal(
            notification.DBusNotificationPresenter.PATH,
            notification.DBusNotificationPresenter.INTERFACE,
            "NotificationClosed")

        # The 2 here is the notification removal reason ("dismissed by the user")
        # it's effectively arbitrary as we don't use that information
        message.setArguments([_as_uint32(notification_id), _as_uint32(2)])
        if not self._bus.send(message):
            raise OSError("Could not send close notification")

    def click(self, notification_id: int) -> None:
        """Sends a click (default action) notification for the given ID."""
        self.action(notification_id, "default")

    def action(self, notification_id: int, name: str) -> None:
        """Sends an action notification for the given ID."""
        message = QDBusMessage.createSignal(
            notification.DBusNotificationPresenter.PATH,
            notification.DBusNotificationPresenter.INTERFACE,
            "ActionInvoked")

        message.setArguments([_as_uint32(notification_id), name])
        if not self._bus.send(message):
            raise OSError("Could not send action notification")

    # Everything below is exposed via DBus
    # pylint: disable=invalid-name

    @pyqtSlot(QDBusMessage, result="uint")
    def Notify(self, dbus_message: QDBusMessage) -> QDBusArgument:
        assert dbus_message.signature() == 'susssasa{sv}i'
        assert dbus_message.type() == QDBusMessage.MethodCallMessage

        message = self._parse_notify_args(*dbus_message.arguments())

        if message.replaces_id == 0:
            message_id = next(self._message_id_gen)
        else:
            message_id = message.replaces_id
        self.messages[message_id] = message

        return message_id

    @pyqtSlot(QDBusMessage, result="QStringList")
    def GetCapabilities(self, message: QDBusMessage) -> List[str]:
        assert not message.signature()
        assert not message.arguments()
        assert message.type() == QDBusMessage.MethodCallMessage

        capabilities = ["actions"]
        if self.supports_body_markup:
            capabilities.append("body-markup")
        return capabilities


@pytest.fixture
def notification_server(qapp):
    if utils.is_windows:
        # The QDBusConnection destructor seems to cause error messages (and potentially
        # segfaults) on Windows, so we bail out early in that case. We still try to get
        # a connection on macOS, since it's theoretically possible to run DBus there.
        pytest.skip("Skipping DBus on Windows")

    server = TestNotificationServer(notification.DBusNotificationPresenter.TEST_SERVICE)
    registered = server.register()
    if not registered:
        assert not (utils.is_linux and testutils.ON_CI), "Expected DBus on Linux CI"
        pytest.skip("No DBus server available")

    yield server
    server.unregister()
