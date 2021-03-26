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
import itertools
import functools
from typing import Any, Dict, Optional, TYPE_CHECKING

from PyQt5.QtCore import (Qt, QObject, QVariant, QMetaType, QByteArray, pyqtSlot,
                          pyqtSignal, QTimer)
from PyQt5.QtGui import QImage, QIcon, QPixmap
from PyQt5.QtDBus import (QDBusConnection, QDBusInterface, QDBus,
                          QDBusArgument, QDBusMessage, QDBusError)
from PyQt5.QtWidgets import QSystemTrayIcon

if TYPE_CHECKING:
    # putting these behind TYPE_CHECKING also means this module is importable
    # on installs that don't have these
    from PyQt5.QtWebEngineCore import QWebEngineNotification
    from PyQt5.QtWebEngineWidgets import QWebEngineProfile

from qutebrowser.config import config
from qutebrowser.misc import objects
from qutebrowser.utils import qtutils, log, utils, debug, message


bridge: Optional['NotificationBridgePresenter'] = None


def init() -> None:
    """Initialize the DBus notification presenter, if applicable.

    If the user doesn't want a notification presenter or it's not supported,
    this method does nothing.

    Always succeeds, but might log an error.
    """
    if config.val.content.notifications.presenter == "qt":
        # In theory, we could somehow postpone the install if the user switches to "qt"
        # at a later point in time. However, doing so is probably too complex compared
        # to its usefulness.
        return

    global bridge
    bridge = NotificationBridgePresenter()


class Error(Exception):
    """Raised when something goes wrong with notifications."""


class AbstractNotificationAdapter(QObject):

    close_id = pyqtSignal(int)
    click_id = pyqtSignal(int)

    def present(
        self,
        qt_notification: "QWebEngineNotification",
        *,
        replaces_id: Optional[int],
    ) -> int:
        raise NotImplementedError


class NotificationBridgePresenter(QObject):

    """Notification presenter which bridges notifications to an adapter."""

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        if not qtutils.version_check('5.14'):
            raise Error("Custom notifications are not supported on Qt < 5.14")

        self._active_notifications: Dict[int, 'QWebEngineNotification'] = {}
        self._adapter: Optional[AbstractNotificationAdapter] = None

        config.instance.changed.connect(self.on_config_changed)

    @config.change_filter('content.notifications.presenter')
    def on_config_changed(self):
        self._init_adapter()

    def _init_adapter(self):
        """Initialize the adapter to use based on the config."""
        setting = config.val.content.notifications.presenter
        log.init.debug(f"Setting up notification adapter ({setting})...")

        if setting == "qt":
            message.error("Can't switch to qt notification presenter at runtime.")
            setting = "auto"

        if setting in ["auto", "libnotify"]:
            candidates = [
                DBusNotificationAdapter,
                SystrayNotificationAdapter,
                MessagesNotificationAdapter,
            ]
        elif setting == "systray":
            candidates = [
                SystrayNotificationAdapter,
                DBusNotificationAdapter,
                MessagesNotificationAdapter,
            ]
        elif setting == "messages":
            candidates = [MessagesNotificationAdapter]  # always succeeds
        else:
            raise utils.Unrachable(setting)

        for candidate in candidates:
            try:
                self._adapter = candidate()
            except Error as e:
                msg = f"Failed to initialize {candidate.NAME} presenter: {e}"
                if setting == "auto":  # silent errors as we want auto fallback
                    log.init.debug(msg)
                elif setting == "libnotify":
                    message.error(msg)
            else:
                break

        self._adapter.click_id.connect(self._on_adapter_clicked)
        self._adapter.close_id.connect(self._on_adapter_closed)

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
                self.present(qt_notification)
            profile.setNotificationPresenter(_present_and_reset)
        else:
            profile.setNotificationPresenter(self.present)

    def present(self, qt_notification: "QWebEngineNotification") -> None:
        """Shows a notification using the configured adapter.

        This should *not* be directly passed to setNotificationPresenter on
        PyQtWebEngine < 5.15 because of a bug in the PyQtWebEngine bindings.
        """
        if self._adapter is None:
            self._init_adapter()
            assert self._adapter is not None

        replaces_id = self._find_replaces_id(qt_notification)
        notification_id = self._adapter.present(
            qt_notification, replaces_id=replaces_id)

        if notification_id <= 0:
            raise Error(f"Got invalid notification id {notification_id}")

        if replaces_id is None:
            if notification_id in self._active_notifications:
                raise Error(f"Got duplicate id {notification_id}")
        elif replaces_id != notification_id:
            raise Error(f"Wanted to replace notification {replaces_id} but got "
                        f"new id {notification_id}.")

        log.webview.debug(f"Sent out notification {notification_id}")
        qt_notification.show()
        self._active_notifications[notification_id] = qt_notification

        qt_notification.closed.connect(functools.partial(
            self._adapter.on_web_closed, notification_id))

    def _find_replaces_id(
        self,
        new_notification: "QWebEngineNotification",
    ) -> Optional[int]:
        """Find an existing notification to replace.

        If no notification should be replaced or the notification to be replaced was not
        found, this returns None.
        """
        if not new_notification.tag():
            return None

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

        return None

    @pyqtSlot(int)
    def _on_adapter_closed(self, notification_id: int) -> None:
        notification = self._active_notifications.get(notification_id)
        if notification is None:
            # Notification from a different application
            return

        del self._active_notifications[notification_id]
        try:
            notification.close()
        except RuntimeError:
            # WORKAROUND for
            # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
            log.misc.debug(f"Ignoring close request for notification {notification_id} "
                           "due to PyQt bug")

    @pyqtSlot(int)
    def _on_adapter_clicked(self, notification_id: int) -> None:
        notification = self._active_notifications.get(notification_id)
        if notification is None:
            # Notification from a different application
            return

        try:
            notification.click()
        except RuntimeError:
            # WORKAROUND for
            # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
            log.misc.debug(f"Ignoring click request for notification {notification_id} "
                           "due to PyQt bug")


class SystrayNotificationAdapter(AbstractNotificationAdapter):

    """Shows notifications using QSystemTrayIcon.

    This is essentially a reimplementation of QtWebEngine's default implementation:
    https://github.com/qt/qtwebengine/blob/v5.15.2/src/webenginewidgets/api/qwebenginenotificationpresenter.cpp

    It exists because QtWebEngine won't allow us to restore its default presenter, so if
    something goes wrong when trying to e.g. connect to the DBus one, we still want to
    be able to switch back after our presenter is already installed. Also, it's nice if
    users can switch presenters in the config live.
    """

    NAME = "systray"
    NOTIFICATION_ID = 1  # only one concurrent ID supported

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            raise Error("No system tray available")
        if not QSystemTrayIcon.supportsMessages():
            raise Error("System tray does not support messages")

        self._systray = QSystemTrayIcon(self)
        self._systray.setIcon(objects.qapp.windowIcon())
        self._systray.messageClicked.connect(self._on_systray_clicked)

    def present(
        self,
        qt_notification: "QWebEngineNotification",
        *,
        replaces_id: Optional[int],
    ) -> int:
        utils.unused(replaces_id)  # QSystemTray can only show one message
        self.close_id.emit(self.NOTIFICATION_ID)
        self._systray.show()
        icon = self._convert_icon(qt_notification.icon())
        self._systray.showMessage(qt_notification.title(), qt_notification.message(), icon)
        return self.NOTIFICATION_ID

    def _convert_icon(self, image: QImage) -> QIcon:
        """Convert a QImage to a QIcon."""
        if image.isNull():
            return QIcon()
        pixmap = QPixmap.fromImage(image, Qt.NoFormatConversion)
        assert not pixmap.isNull()
        icon = QIcon(pixmap)
        assert not icon.isNull()
        return icon

    @pyqtSlot()
    def _on_systray_clicked(self) -> None:
        self.on_clicked.emit(self.NOTIFICATION_ID)

    @pyqtSlot(int)
    def on_web_closed(self, notification_id: int) -> None:
        assert notification_id == self.NOTIFICATION_ID, notification_id
        self._systray.hide()


class MessagesNotificationAdapter(AbstractNotificationAdapter):

    """Shows notifications using qutebrowser messages.

    This is mostly used as a fallback if no other method is available. Most notification
    features are not supported.
    """

    NAME = "messages"

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self._id_gen = itertools.count(1)

    def present(
        self,
        qt_notification: "QWebEngineNotification",
        *,
        replaces_id: Optional[int],
    ) -> int:
        url = html.escape(qt_notification.origin().toDisplayString())
        title = html.escape(qt_notification.title())
        body = html.escape(qt_notification.message())
        hint = "" if qt_notification.icon().isNull() else " (image not shown)"

        new_id = replaces_id if replaces_id is not None else next(self._id_gen)
        markup = (
            f"<i>Notification from {url}:{hint}</i><br/><br/>"
            f"<b>{title}</b><br/>"
            f"{body}"
        )
        message.info(markup, replace=f'notifications-{new_id}')

        # Faking closing, timing might not be 100% accurate
        QTimer.singleShot(config.val.messages.timeout, lambda: self.close_id.emit(new_id))

        return new_id

    @pyqtSlot(int)
    def on_web_closed(self, _notification_id: int) -> None:
        """We can't close messages."""
        pass


@dataclasses.dataclass
class _ServerQuirks:

    """Quirks for certain notification servers."""

    spec_version: Optional[str] = None
    avoid_actions: bool = False
    icon_key: Optional[str] = None


class DBusNotificationAdapter(AbstractNotificationAdapter):

    """Sends notifications over DBus."""

    SERVICE = "org.freedesktop.Notifications"
    TEST_SERVICE = "org.qutebrowser.TestNotifications"
    PATH = "/org/freedesktop/Notifications"
    INTERFACE = "org.freedesktop.Notifications"
    SPEC_VERSION = "1.2"  # Released in January 2011, still current in March 2021.
    NAME = "libnotify"

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(bridge)
        if not qtutils.version_check('5.14'):
            raise Error("Notifications are not supported on Qt < 5.14")

        if utils.is_windows:
            # The QDBusConnection destructor seems to cause error messages (and
            # potentially segfaults) on Windows, so we bail out early in that case.
            # We still try to get a connection on macOS, since it's theoretically
            # possible to run DBus there.
            raise Error("libnotify is not supported on Windows")

        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            raise Error(
                "Failed to connect to DBus session bus: " +
                self._dbus_error_str(bus.lastError()))

        test_service = 'test-notification-service' in objects.debug_flags
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

    def present(
        self,
        qt_notification: "QWebEngineNotification",
        *,
        replaces_id: Optional[int],
    ) -> int:
        """Shows a notification over DBus."""
        # We can't just pass the int because it won't get sent as the right type.
        if replaces_id is None:
            replaces_id = 0  # 0 is never a valid ID according to the spec
        replaces_id_arg = QVariant(replaces_id)
        replaces_id_arg.convert(QVariant.UInt)

        actions = []
        if 'actions' in self._capabilities:
            actions = ['default', '']  # key, name
        actions_arg = QDBusArgument(actions, QMetaType.QStringList)

        hints: Dict[str, Any] = {
            # Include the origin in case the user wants to do different things
            # with different origin's notifications.
            "x-qutebrowser-origin": qt_notification.origin().toDisplayString(),
            "desktop-entry": "org.qutebrowser.qutebrowser",
        }

        icon = qt_notification.icon()
        if icon.isNull():
            filename = ':/icons/qutebrowser-64x64.png'  # FIXME size?
            icon = QImage(filename)

        key = self._quirks.icon_key or "image-data"
        hints[key] = self._convert_image(icon)

        reply = self.interface.call(
            QDBus.BlockWithGui,
            "Notify",
            "qutebrowser",  # application name
            replaces_id_arg,  # replaces notification id
            "",  # icon name/file URL, we use image-data and friends instead.
            # Titles don't support markup, so no need to escape them.
            qt_notification.title(),
            self._format_body(qt_notification.message()),
            actions_arg,
            hints,
            -1,  # timeout; -1 means 'use default'
        )
        self._verify_message(reply, "u", QDBusMessage.ReplyMessage)
        return reply.arguments()[0]  # notification ID

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
        bytes_per_line = qimage.bytesPerLine()
        width = qimage.width()
        height = qimage.height()

        image_data = QDBusArgument()
        image_data.beginStructure()
        image_data.add(width)
        image_data.add(height)
        image_data.add(bytes_per_line)
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

        # Despite the spec not mandating this, many notification daemons mandate that
        # the last scanline does not have any padding bytes.
        #
        # Or in the words of dunst:
        #
        #     The image is serialised rowwise pixel by pixel. The rows are aligned by a
        #     spacer full of garbage. The overall data length of data + garbage is
        #     called the rowstride.
        #
        #     Mind the missing spacer at the last row.
        #
        #     len:     |<--------------rowstride---------------->|
        #     len:     |<-width*pixelstride->|
        #     row 1:   |   data for row 1    | spacer of garbage |
        #     row 2:   |   data for row 2    | spacer of garbage |
        #              |         .           | spacer of garbage |
        #              |         .           | spacer of garbage |
        #              |         .           | spacer of garbage |
        #     row n-1: |   data for row n-1  | spacer of garbage |
        #     row n:   |   data for row n    |
        #
        # Source:
        # https://github.com/dunst-project/dunst/blob/v1.6.1/src/icon.c#L292-L309
        padding = bytes_per_line - width * channel_count
        assert 0 <= padding < 3, padding
        size -= padding

        bits = qimage.constBits().asstring(size)
        image_data.add(QByteArray(bits))

        image_data.endStructure()
        return image_data

    @pyqtSlot(QDBusMessage)
    def _handle_close(self, msg: QDBusMessage) -> None:
        self._verify_message(msg, "uu", QDBusMessage.SignalMessage)
        notification_id, _close_reason = msg.arguments()
        self.close_id.emit(notification_id)

    @pyqtSlot(QDBusMessage)
    def _handle_action(self, msg: QDBusMessage) -> None:
        self._verify_message(msg, "us", QDBusMessage.SignalMessage)
        notification_id, action_key = msg.arguments()
        if action_key == "default":
            self.click_id.emit(notification_id)

    @pyqtSlot(int)
    def on_web_closed(self, notification_id: int) -> None:
        id_arg = QVariant(notification_id)
        id_arg.convert(QVariant.UInt)
        self.interface.call(QDBus.NoBlock, "CloseNotification", id_arg)

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
