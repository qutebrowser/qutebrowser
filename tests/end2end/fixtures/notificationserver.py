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
        assert replaces_id == 0
        assert icon == "qutebrowser"
        assert actions == []
        assert list(hints) == ['x-qutebrowser-origin']
        assert hints['x-qutebrowser-origin'].startswith('http://localhost:')
        assert timeout == -1
        return NotificationProperties(title=title, body=body)

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

    # Everything below is exposed via DBus
    # pylint: disable=invalid-name

    @pyqtSlot(QDBusMessage, result="uint")
    def Notify(self, message: QDBusMessage) -> QDBusArgument:
        message_id = next(self._message_id_gen)
        args = message.arguments()
        self.messages[message_id] = self._parse_notify_args(*args)
        return message_id

    @pyqtSlot(QDBusMessage, result="QStringList")
    def GetCapabilities(self, message: QDBusMessage) -> List[str]:
        assert not message.arguments()
        return ["body-markup"] if self.supports_body_markup else []


@pytest.fixture
def notification_server(qapp):
    server = TestNotificationServer(notification.DBusNotificationPresenter.TEST_SERVICE)
    registered = server.register()
    if not registered:
        assert not (utils.is_linux and testutils.ON_CI), "Expected DBus on Linux CI"
        pytest.skip("No DBus server available")

    yield server
    server.unregister()
