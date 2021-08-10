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

from PyQt5.QtCore import QObject, QByteArray, QUrl, pyqtSlot
from PyQt5.QtGui import QImage
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
    img_width: int
    img_height: int
    closed_via_web: bool = False


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
        self.last_id = None

    def cleanup(self) -> None:
        self.messages = {}

    def last_msg(self) -> NotificationProperties:
        return self.messages[self.last_id]

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
            notification.DBusNotificationAdapter.PATH,
            notification.DBusNotificationAdapter.INTERFACE,
            self,
            QDBusConnection.ExportAllSlots,
        )
        return True

    def unregister(self) -> None:
        self._bus.unregisterObject(notification.DBusNotificationAdapter.PATH)
        assert self._bus.unregisterService(self._service)

    def _parse_notify_args(self, appname, replaces_id, icon, title, body, actions,
                           hints, timeout) -> NotificationProperties:
        """Parse a Notify dbus reply.

        Checks all constant values and returns a NotificationProperties object for
        values being checked inside test cases.
        """
        assert appname == "qutebrowser"
        assert icon == ''  # using icon data
        assert actions == ['default', 'Activate']
        assert timeout == -1

        assert hints.keys() == {
            "x-qutebrowser-origin",
            "x-kde-origin-name",
            "desktop-entry",
            "image-data",
        }
        for key in 'x-qutebrowser-origin', 'x-kde-origin-name':
            value = hints[key]
            url = QUrl(value)
            assert url.isValid(), value
            assert url.scheme() == 'http', value
            assert url.host() == 'localhost', value

        assert hints['desktop-entry'] == 'org.qutebrowser.qutebrowser'

        img = self._parse_image(*hints["image-data"])

        if replaces_id != 0:
            assert replaces_id in self.messages

        return NotificationProperties(title=title, body=body, replaces_id=replaces_id,
                                      img_width=img.width(), img_height=img.height())

    def _parse_image(
            self,
            width: int,
            height: int,
            bytes_per_line: int,
            has_alpha: bool,
            bits_per_color: int,
            channel_count: int,
            data: QByteArray,
    ) -> QImage:
        """Make sure the given image data is valid and return a QImage."""
        # Chromium limit?
        assert 0 < width <= 320
        assert 0 < height <= 320

        # Based on dunst:
        # https://github.com/dunst-project/dunst/blob/v1.6.1/src/icon.c#L336-L348
        # (A+7)/8 rounds up A to the next byte boundary
        pixelstride = (channel_count * bits_per_color + 7) // 8
        expected_len = (height - 1) * bytes_per_line + width * pixelstride
        assert len(data) == expected_len

        assert bits_per_color == 8
        assert channel_count == (4 if has_alpha else 3)
        assert bytes_per_line >= width * channel_count

        qimage_format = QImage.Format_RGBA8888 if has_alpha else QImage.Format_RGB888
        img = QImage(data, width, height, bytes_per_line, qimage_format)
        assert not img.isNull()
        assert img.width() == width
        assert img.height() == height

        return img

    def close(self, notification_id: int) -> None:
        """Sends a close notification for the given ID."""
        message = QDBusMessage.createSignal(
            notification.DBusNotificationAdapter.PATH,
            notification.DBusNotificationAdapter.INTERFACE,
            "NotificationClosed")

        # The 2 here is the notification removal reason ("dismissed by the user")
        # it's effectively arbitrary as we don't use that information
        message.setArguments([
            notification._as_uint32(notification_id),
            notification._as_uint32(2),
        ])
        if not self._bus.send(message):
            raise OSError("Could not send close notification")

    def click(self, notification_id: int) -> None:
        """Sends a click (default action) notification for the given ID."""
        self.action(notification_id, "default")

    def action(self, notification_id: int, name: str) -> None:
        """Sends an action notification for the given ID."""
        message = QDBusMessage.createSignal(
            notification.DBusNotificationAdapter.PATH,
            notification.DBusNotificationAdapter.INTERFACE,
            "ActionInvoked")

        message.setArguments([notification._as_uint32(notification_id), name])
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

        self.last_id = message_id
        return message_id

    @pyqtSlot(QDBusMessage, result="QStringList")
    def GetCapabilities(self, message: QDBusMessage) -> List[str]:
        assert not message.signature()
        assert not message.arguments()
        assert message.type() == QDBusMessage.MethodCallMessage

        capabilities = ["actions", "x-kde-origin-name"]
        if self.supports_body_markup:
            capabilities.append("body-markup")

        return capabilities

    @pyqtSlot(QDBusMessage)
    def CloseNotification(self, dbus_message: QDBusMessage) -> None:
        assert dbus_message.signature() == 'u'
        assert dbus_message.type() == QDBusMessage.MethodCallMessage

        message_id = dbus_message.arguments()[0]
        self.messages[message_id].closed_via_web = True


@pytest.fixture(scope='module')
def notification_server(qapp):
    if utils.is_windows:
        # The QDBusConnection destructor seems to cause error messages (and potentially
        # segfaults) on Windows, so we bail out early in that case. We still try to get
        # a connection on macOS, since it's theoretically possible to run DBus there.
        pytest.skip("Skipping DBus on Windows")

    server = TestNotificationServer(notification.DBusNotificationAdapter.TEST_SERVICE)
    registered = server.register()
    if not registered:
        assert not (utils.is_linux and testutils.ON_CI), "Expected DBus on Linux CI"
        pytest.skip("No DBus server available")

    yield server
    server.unregister()
