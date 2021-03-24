# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Handles sending notifications over DBus.

Related spec: https://developer.gnome.org/notification-spec/
"""

import html
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from PyQt5.QtGui import QImage
from PyQt5.QtCore import (QObject, QVariant, QMetaType, QByteArray, pyqtSlot,
                          PYQT_VERSION)
from PyQt5.QtDBus import (QDBusConnection, QDBusInterface, QDBus,
                          QDBusArgument, QDBusMessage)

if TYPE_CHECKING:
    # putting these behind TYPE_CHECKING also means this module is importable
    # on installs that don't have these
    from PyQt5.QtWebEngineCore import QWebEngineNotification
    from PyQt5.QtWebEngineWidgets import QWebEngineProfile

from qutebrowser.config import config
from qutebrowser.misc import objects
from qutebrowser.utils import qtutils, log, utils, debug


dbus_presenter: Optional['DBusNotificationPresenter'] = None


def init() -> None:
    """Initialize the DBus notification presenter, if applicable.

    If the user doesn't want a notification presenter or it's not supported,
    this method does nothing.

    Always succeeds, but might log an error.
    """
    should_use_dbus = (
        qtutils.version_check("5.13") and
        config.val.content.notification_presenter == "libnotify" and
        # Don't even try to use DBus notifications on platforms that won't have
        # it supported.
        not utils.is_windows and
        not utils.is_mac
    )
    if not should_use_dbus:
        return

    global dbus_presenter
    log.init.debug("Setting up DBus notification presenter...")
    testing = 'test-notification-service' in objects.debug_flags
    try:
        dbus_presenter = DBusNotificationPresenter(testing)
    except DBusException as e:
        log.init.error(f"Failed to initialize DBus notification presenter: {e}")


class DBusException(Exception):
    """Raised when something goes wrong with talking to DBus."""


class DBusNotificationPresenter(QObject):
    """Manages notifications that are sent over DBus."""

    SERVICE = "org.freedesktop.Notifications"
    TEST_SERVICE = "org.qutebrowser.TestNotifications"
    PATH = "/org/freedesktop/Notifications"
    INTERFACE = "org.freedesktop.Notifications"

    def __init__(self, test_service: bool = False):
        super().__init__()
        self._active_notifications: Dict[int, 'QWebEngineNotification'] = {}
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            raise DBusException("Failed to connect to DBus session bus")

        service = self.TEST_SERVICE if test_service else self.SERVICE

        self.interface = QDBusInterface(
            service,
            self.PATH,
            self.INTERFACE,
            bus,
        )
        if not self.interface.isValid():
            raise DBusException("Could not construct a DBus interface")

        if not bus.connect(
            service,
            self.PATH,
            self.INTERFACE,
            "NotificationClosed",
            self._handle_close,
        ):
            raise DBusException("Could not connect to NotificationClosed")

        if not bus.connect(
            service,
            self.PATH,
            self.INTERFACE,
            "ActionInvoked",
            self._handle_action,
        ):
            raise DBusException("Could not connect to ActionInvoked")

        if not test_service:
            # Can't figure out how to make this work with the test server...
            # https://www.riverbankcomputing.com/pipermail/pyqt/2021-March/043724.html
            ping_reply = self.interface.call(
                QDBus.BlockWithGui,
                "GetServerInformation",
            )
            self._verify_message(ping_reply, "ssss", QDBusMessage.ReplyMessage)
            name, vendor, version, spec_version = ping_reply.arguments()
            log.init.debug("Connected to notification server: "
                           f"{name} {version} by {vendor}, "
                           f"implementing spec {spec_version}")
            if spec_version != "1.2":
                # Released in January 2011, still current in March 2021.
                log.init.warn(f"Notification server ({name} {version} by {vendor}) "
                              f"implements spec {spec_version}, but 1.2 was expected. "
                              f"If {name} is up to date, please report a bug.")

        # None means we don't know yet.
        self._capabilities: Optional[List[str]] = None

    def install(self, profile: "QWebEngineProfile") -> None:
        """Sets the profile to use the manager as the presenter."""
        # WORKAROUND for
        # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042916.html
        # Fixed in PyQtWebEngine 5.15.0

        try:
            from PyQt5.QtWebEngine import PYQT_WEBENGINE_VERSION
        except ImportError:
            PYQT_WEBENGINE_VERSION = None  # type: ignore[assignment]

        if PYQT_WEBENGINE_VERSION is None or PYQT_WEBENGINE_VERSION < 0x050F00:
            # PyQtWebEngine unrefs the callback after it's called, for some
            # reason.  So we call setNotificationPresenter again to *increase*
            # its refcount to prevent it from getting GC'd. Otherwise, random
            # methods start getting called with the notification as `self`, or
            # segfaults happen, or other badness.
            def _present_and_reset(qt_notification: "QWebEngineNotification") -> None:
                profile.setNotificationPresenter(_present_and_reset)
                self._present(qt_notification)
            profile.setNotificationPresenter(_present_and_reset)
        else:
            profile.setNotificationPresenter(self._present)

    def _verify_message(
        self,
        message: QDBusMessage,
        expected_signature: str,
        expected_type: QDBusMessage.MessageType,
    ) -> None:
        """Check the signature/type of a received message.

        Raises DBusError if the signature doesn't match.
        """
        assert expected_type not in [
            QDBusMessage.ErrorMessage,
            QDBusMessage.InvalidMessage,
        ], expected_type

        if message.type() == QDBusMessage.ErrorMessage:
            raise DBusException(f"Got DBus error: {message.errorMessage()}")

        signature = message.signature()
        if signature != expected_signature:
            raise DBusException(
                f"Got a message with signature {signature} but expected "
                f"{expected_signature} (args: {message.arguments()})")

        typ = message.type()
        if typ != expected_type:
            type_str = debug.qenum_key(QDBusMessage.MessageType, typ)
            expected_type_str = debug.qenum_key(QDBusMessage.MessageType, expected_type)
            raise DBusException(
                f"Got a message of type {type_str} but expected {expected_type_str}"
                f"(args: {message.arguments()})")

    def _find_matching_id(self, new_notification: "QWebEngineNotification") -> int:
        """Find an existing notification to replace.

        If no notification should be replaced or the notification to be replaced was not
        found, this returns 0 (as per the notification spec).
        """
        if not new_notification.tag():
            return 0
        for notification_id, notification in self._active_notifications.items():
            if notification.matches(new_notification):
                return notification_id
        return 0

    def _present(self, qt_notification: "QWebEngineNotification") -> None:
        """Shows a notification over DBus.

        This should *not* be directly passed to setNotificationPresenter on
        PyQtWebEngine < 5.15 because of a bug in the PyQtWebEngine bindings.
        """
        # Deferring this check to the first presentation means we can tweak
        # whether the test notification server supports body markup.
        if self._capabilities is None:
            self._fetch_capabilities()
            assert self._capabilities is not None

        # We can't just pass the int because it won't get sent as the right type.
        existing_id = self._find_matching_id(qt_notification)
        existing_id_arg = QVariant(existing_id)
        existing_id_arg.convert(QVariant.UInt)

        actions = []
        if 'actions' in self._capabilities:
            actions = ['default', '']  # key, name
        actions_arg = QDBusArgument(actions, QMetaType.QStringList)

        qt_notification.show()
        hints: Dict[str, Any] = {
            # Include the origin in case the user wants to do different things
            # with different origin's notifications.
            "x-qutebrowser-origin": qt_notification.origin().toDisplayString(),
            "desktop-entry": "org.qutebrowser.qutebrowser",
        }
        if not qt_notification.icon().isNull():
            hints["image-data"] = self._convert_image(qt_notification.icon())

        reply = self.interface.call(
            QDBus.BlockWithGui,
            "Notify",
            "qutebrowser",  # application name
            existing_id_arg,  # replaces notification id
            "qutebrowser",  # icon (freedesktop.org icon theme name)
            # Titles don't support markup, so no need to escape them.
            qt_notification.title(),
            self._format_body(qt_notification.message()),
            actions_arg,
            hints,
            -1,  # timeout; -1 means 'use default'
        )
        self._verify_message(reply, "u", QDBusMessage.ReplyMessage)

        notification_id = reply.arguments()[0]
        if existing_id != 0 and notification_id != existing_id:
            raise DBusException(f"Wanted to replace notification {existing_id} but got "
                                f"new id {notification_id}.")
        if notification_id == 0:
            raise DBusException("Got invalid notification id 0")

        self._active_notifications[notification_id] = qt_notification
        log.webview.debug(f"Sent out notification {notification_id}")

    def _convert_image(self, qimage: QImage) -> QDBusArgument:
        """Converts a QImage to the structure DBus expects."""
        # This is apparently what GTK-based notification daemons expect; tested
        # it with dunst.  Otherwise you get weird color schemes.
        qimage.convertTo(QImage.Format_RGBA8888)
        image_data = QDBusArgument()
        image_data.beginStructure()
        image_data.add(qimage.width())
        image_data.add(qimage.height())
        image_data.add(qimage.bytesPerLine())
        image_data.add(qimage.hasAlphaChannel())
        # RGBA_8888 always has 8 bits per color, 4 channels.
        image_data.add(8)
        image_data.add(4)
        try:
            size = qimage.sizeInBytes()
        except TypeError:
            # WORKAROUND for
            # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042919.html
            # byteCount() is obsolete, but sizeInBytes() is only available with
            # SIP >= 5.3.0.
            size = qimage.byteCount()
        bits = qimage.constBits().asstring(size)
        image_data.add(QByteArray(bits))
        image_data.endStructure()
        return image_data

    @pyqtSlot(QDBusMessage)
    def _handle_close(self, message: QDBusMessage) -> None:
        self._verify_message(message, "uu", QDBusMessage.SignalMessage)

        notification_id, _close_reason = message.arguments()
        notification = self._active_notifications.get(notification_id)
        if notification is not None:
            try:
                notification.close()
            except RuntimeError:
                # WORKAROUND for
                # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
                pass

    @pyqtSlot(QDBusMessage)
    def _handle_action(self, message: QDBusMessage) -> None:
        self._verify_message(message, "us", QDBusMessage.SignalMessage)

        notification_id, action_key = message.arguments()
        if action_key != "default":
            raise DBusException(f"Got unknown action {action_key}")

        notification = self._active_notifications.get(notification_id)
        if notification is not None:
            try:
                notification.click()
            except RuntimeError:
                # WORKAROUND for
                # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
                pass

    def _fetch_capabilities(self) -> None:
        """Fetch capabilities from the notification server."""
        reply = self.interface.call(
            QDBus.BlockWithGui,
            "GetCapabilities",
        )
        self._verify_message(reply, "as", QDBusMessage.ReplyMessage)
        self._capabilities = reply.arguments()[0]
        log.misc.debug(f"Notification server capabilities: {self._capabilities}")

    def _format_body(self, message: str) -> str:
        assert self._capabilities is not None
        if 'body-markup' in self._capabilities:
            return html.escape(message)
        return message
