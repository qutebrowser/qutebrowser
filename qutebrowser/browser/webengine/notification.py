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

Related specs:

https://developer.gnome.org/notification-spec/
https://specifications.freedesktop.org/notification-spec/notification-spec-latest.html
"""

import html
import dataclasses
from typing import Any, Dict, Optional, TYPE_CHECKING

from PyQt5.QtGui import QImage
from PyQt5.QtCore import QObject, QVariant, QMetaType, QByteArray, pyqtSlot
from PyQt5.QtDBus import (QDBusConnection, QDBusInterface, QDBus,
                          QDBusArgument, QDBusMessage, QDBusError)

if TYPE_CHECKING:
    # putting these behind TYPE_CHECKING also means this module is importable
    # on installs that don't have these
    from PyQt5.QtWebEngineCore import QWebEngineNotification
    from PyQt5.QtWebEngineWidgets import QWebEngineProfile

from qutebrowser.config import config
from qutebrowser.misc import objects
from qutebrowser.utils import qtutils, log, utils, debug, message


dbus_presenter: Optional['DBusNotificationPresenter'] = None


def init() -> None:
    """Initialize the DBus notification presenter, if applicable.

    If the user doesn't want a notification presenter or it's not supported,
    this method does nothing.

    Always succeeds, but might log an error.
    """
    setting = config.val.content.notifications.presenter
    if setting not in ["auto", "libnotify"]:
        return

    global dbus_presenter
    log.init.debug("Setting up DBus notification presenter...")
    testing = 'test-notification-service' in objects.debug_flags
    try:
        dbus_presenter = DBusNotificationPresenter(testing)
    except Error as e:
        msg = f"Failed to initialize DBus notification presenter: {e}"
        if setting == "libnotify":
            # Explicitly set to "libnotify", so show the error to the user.
            message.error(msg)
        elif setting == "auto":
            log.init.debug(msg)
        else:
            raise utils.Unreachable(setting)


class Error(Exception):
    """Raised when something goes wrong with DBusNotificationPresenter."""


@dataclasses.dataclass
class _ServerQuirks:

    """Quirks for certain notification servers."""

    spec_version: Optional[str] = None
    avoid_actions: bool = False
    wrong_replaces_id: bool = False
    icon_key: Optional[str] = None


class DBusNotificationPresenter(QObject):
    """Manages notifications that are sent over DBus."""

    SERVICE = "org.freedesktop.Notifications"
    TEST_SERVICE = "org.qutebrowser.TestNotifications"
    PATH = "/org/freedesktop/Notifications"
    INTERFACE = "org.freedesktop.Notifications"
    SPEC_VERSION = "1.2"  # Released in January 2011, still current in March 2021.

    def __init__(self, test_service: bool = False):
        super().__init__()

        if not qtutils.version_check('5.14'):
            raise Error("Notifications are not supported on Qt < 5.14")

        if utils.is_windows:
            # The QDBusConnection destructor seems to cause error messages (and
            # potentially segfaults) on Windows, so we bail out early in that case.
            # We still try to get a connection on macOS, since it's theoretically
            # possible to run DBus there.
            raise Error("libnotify is not supported on Windows")

        self._active_notifications: Dict[int, 'QWebEngineNotification'] = {}
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            raise Error(
                "Failed to connect to DBus session bus: " +
                self._dbus_error_str(bus.lastError()))

        service = self.TEST_SERVICE if test_service else self.SERVICE

        self.interface = QDBusInterface(service, self.PATH, self.INTERFACE, bus)
        if not self.interface.isValid():
            raise Error(
                "Could not construct a DBus interface: " +
                self._dbus_error_str(self.interface.lastError()))

        connections = [
            ("NotificationClosed", self._handle_close),
            ("ActionInvoked", self._handle_action),
        ]
        for name, func in connections:
            if not bus.connect(service, self.PATH, self.INTERFACE, name, func):
                raise Error(
                    f"Could not connect to {name}: " +
                    self._dbus_error_str(bus.lastError()))

        self._quirks = _ServerQuirks()
        if not test_service:
            # Can't figure out how to make this work with the test server...
            # https://www.riverbankcomputing.com/pipermail/pyqt/2021-March/043724.html
            self._get_server_info()

        self._fetch_capabilities()

    def _get_server_info(self) -> None:
        """Query notification server information and set quirks."""
        reply = self.interface.call(QDBus.BlockWithGui, "GetServerInformation")
        self._verify_message(reply, "ssss", QDBusMessage.ReplyMessage)
        name, vendor, version, spec_version = reply.arguments()

        log.init.debug(
            f"Connected to notification server: {name} {version} by {vendor}, "
            f"implementing spec {spec_version}")

        all_quirks = {
            # Shows a dialog box instead of a notification bubble as soon as a
            # notification has an action (even if only a default one). Dialog boxes are
            # buggy and return a notification with ID 0.
            ("notify-osd", "Canonical Ltd"):
                _ServerQuirks(avoid_actions=True, spec_version="1.1"),

            # Still in active development but doesn't implement spec 1.2:
            # https://github.com/mate-desktop/mate-notification-daemon/issues/132
            ("Notification Daemon", "MATE"): _ServerQuirks(spec_version="1.1"),

            # Still in active development but spec 1.0/1.2 support isn't
            # released yet:
            # https://github.com/awesomeWM/awesome/commit/e076bc664e0764a3d3a0164dabd9b58d334355f4
            # Thus, no icon/image support at the moment...
            ("naughty", "awesome"): _ServerQuirks(spec_version="1.0"),

            # https://gitlab.xfce.org/apps/xfce4-notifyd/-/issues/48
            ("Xfce Notify Daemon", "Xfce"): _ServerQuirks(wrong_replaces_id=True),
        }
        quirks = all_quirks.get((name, vendor))
        if quirks is not None:
            log.init.debug(f"Enabling quirks {quirks}")
            self._quirks = quirks

        expected_spec_version = self._quirks.spec_version or self.SPEC_VERSION
        if spec_version != expected_spec_version:
            log.init.warning(
                f"Notification server ({name} {version} by {vendor}) implements "
                f"spec {spec_version}, but {expected_spec_version} was expected. "
                f"If {name} is up to date, please report a qutebrowser bug.")

        # https://specifications.freedesktop.org/notification-spec/latest/ar01s08.html
        icon_key_overrides = {
            "1.0": "icon_data",
            "1.1": "image_data",
        }
        self._quirks.icon_key = icon_key_overrides.get(spec_version)

    def _dbus_error_str(self, error: QDBusError) -> str:
        """Get a string for a DBus error."""
        qtutils.ensure_valid(error)
        return f"{error.name()} - {error.message()}"

    def install(self, profile: "QWebEngineProfile") -> None:
        """Sets the profile to use the manager as the presenter."""
        # WORKAROUND for
        # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042916.html
        # Fixed in PyQtWebEngine 5.15.0
        # PYQT_WEBENGINE_VERSION was added with PyQtWebEngine 5.13, but if we're here,
        # we already did a version check above.
        from PyQt5.QtWebEngine import PYQT_WEBENGINE_VERSION
        if PYQT_WEBENGINE_VERSION < 0x050F00:
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
        msg: QDBusMessage,
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

        if msg.type() == QDBusMessage.ErrorMessage:
            raise Error(f"Got DBus error: {msg.errorName()} - {msg.errorMessage()}")

        signature = msg.signature()
        if signature != expected_signature:
            raise Error(
                f"Got a message with signature {signature} but expected "
                f"{expected_signature} (args: {msg.arguments()})")

        typ = msg.type()
        if typ != expected_type:
            type_str = debug.qenum_key(QDBusMessage.MessageType, typ)
            expected_type_str = debug.qenum_key(QDBusMessage.MessageType, expected_type)
            raise Error(
                f"Got a message of type {type_str} but expected {expected_type_str}"
                f"(args: {msg.arguments()})")

    def _find_matching_id(self, new_notification: "QWebEngineNotification") -> int:
        """Find an existing notification to replace.

        If no notification should be replaced or the notification to be replaced was not
        found, this returns 0 (as per the notification spec).
        """
        if not new_notification.tag():
            return 0

        try:
            for notification_id, notification in self._active_notifications.items():
                if notification.matches(new_notification):
                    return notification_id
        except RuntimeError:
            # WORKAROUND for
            # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
            # (also affects .matches)
            log.misc.debug(
                f"Ignoring notification tag {new_notification.tag()!r} due to PyQt bug")

        return 0

    def _present(self, qt_notification: "QWebEngineNotification") -> None:
        """Shows a notification over DBus.

        This should *not* be directly passed to setNotificationPresenter on
        PyQtWebEngine < 5.15 because of a bug in the PyQtWebEngine bindings.
        """
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
            key = self._quirks.icon_key or "image-data"
            hints[key] = self._convert_image(qt_notification.icon())

        reply = self.interface.call(
            QDBus.BlockWithGui,
            "Notify",
            "qutebrowser",  # application name
            existing_id_arg,  # replaces notification id
            "",  # icon name/file URL, we use image-data and friends instead.
            # Titles don't support markup, so no need to escape them.
            qt_notification.title(),
            self._format_body(qt_notification.message()),
            actions_arg,
            hints,
            -1,  # timeout; -1 means 'use default'
        )
        self._verify_message(reply, "u", QDBusMessage.ReplyMessage)

        notification_id = reply.arguments()[0]
        if existing_id not in [0, notification_id]:
            msg = (f"Wanted to replace notification {existing_id} but got new id "
                   f"{notification_id}.")
            if self._quirks.wrong_replaces_id:
                log.webview.debug(msg)
                del self._active_notifications[existing_id]
            else:
                raise Error(msg)

        if notification_id == 0:
            raise Error("Got invalid notification id 0")

        self._active_notifications[notification_id] = qt_notification
        log.webview.debug(f"Sent out notification {notification_id}")

    def _convert_image(self, qimage: QImage) -> QDBusArgument:
        """Converts a QImage to the structure DBus expects."""
        # https://specifications.freedesktop.org/notification-spec/latest/ar01s05.html#icons-and-images-formats
        bits_per_color = 8
        has_alpha = qimage.hasAlphaChannel()
        if has_alpha:
            image_format = QImage.Format_RGBA8888
            channel_count = 4
        else:
            image_format = QImage.Format_RGB888
            channel_count = 3

        qimage.convertTo(image_format)

        image_data = QDBusArgument()
        image_data.beginStructure()
        image_data.add(qimage.width())
        image_data.add(qimage.height())
        image_data.add(qimage.bytesPerLine())
        image_data.add(has_alpha)
        image_data.add(bits_per_color)
        image_data.add(channel_count)
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
    def _handle_close(self, msg: QDBusMessage) -> None:
        self._verify_message(msg, "uu", QDBusMessage.SignalMessage)
        notification_id, _close_reason = msg.arguments()

        notification = self._active_notifications.get(notification_id)
        if notification is None:
            # Notification from a different application
            return

        try:
            notification.close()
        except RuntimeError:
            # WORKAROUND for
            # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
            log.misc.debug(f"Ignoring close request for notification {notification_id} "
                           "due to PyQt bug")

    @pyqtSlot(QDBusMessage)
    def _handle_action(self, msg: QDBusMessage) -> None:
        self._verify_message(msg, "us", QDBusMessage.SignalMessage)
        notification_id, action_key = msg.arguments()

        notification = self._active_notifications.get(notification_id)
        if notification is None:
            # Notification from a different application
            return

        if action_key != "default":
            raise Error(f"Got unknown action {action_key}")

        try:
            notification.click()
        except RuntimeError:
            # WORKAROUND for
            # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
            log.misc.debug(f"Ignoring click request for notification {notification_id} "
                           "due to PyQt bug")

    def _fetch_capabilities(self) -> None:
        """Fetch capabilities from the notification server."""
        reply = self.interface.call(
            QDBus.BlockWithGui,
            "GetCapabilities",
        )
        self._verify_message(reply, "as", QDBusMessage.ReplyMessage)

        self._capabilities = reply.arguments()[0]
        if self._quirks.avoid_actions and 'actions' in self._capabilities:
            self._capabilities.remove('actions')

        log.misc.debug(f"Notification server capabilities: {self._capabilities}")

    def _format_body(self, body: str) -> str:
        if 'body-markup' in self._capabilities:
            return html.escape(body)
        return body
