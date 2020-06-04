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
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Handles sending notifications over DBus."""

import typing

from qutebrowser.utils import log

from PyQt5.QtGui import QImage
from PyQt5.QtCore import QObject, QVariant, QMetaType, QByteArray, pyqtSlot, PYQT_VERSION
from PyQt5.QtDBus import QDBusConnection, QDBusInterface, QDBus, QDBusArgument, QDBusMessage
from PyQt5.QtWebEngine import PYQT_WEBENGINE_VERSION
from PyQt5.QtWebEngineCore import QWebEngineNotification
from PyQt5.QtWebEngineWidgets import QWebEngineProfile


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
        self._active_notifications = {}  # type: typing.Dict[int, QWebEngineNotification]
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

        bus.connect(
            service,
            self.PATH,
            self.INTERFACE,
            "NotificationClosed",
            self._handle_close
        )

        if not self.interface:
            raise DBusException("Could not construct a DBus interface")

    def install(self, profile: QWebEngineProfile) -> None:
        """Sets the profile to use the manager as the presenter."""
        # WORKAROUND for https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042916.html
        if PYQT_VERSION < 0x050F00:  # PyQt 5.15
            # PyQtWebEngine unrefs the callback after it's called, for some reason.
            # So we call setNotificationPresenter again to *increase* its refcount
            # to prevent it from getting GC'd. Otherwise, random methods start
            # getting called with the notification as `self`, or segfaults happen,
            # or other badness.
            def _present_and_reset(qt_notification: QWebEngineNotification) -> None:
                profile.setNotificationPresenter(_present_and_reset)
                self._present(qt_notification)
            profile.setNotificationPresenter(_present_and_reset)
        else:
            profile.setNotificationPresenter(self._present)

    def _present(self, qt_notification: QWebEngineNotification) -> None:
        """Shows a notification over DBus.

        This should *not* be directly passed to setNotificationPresenter
        because of a bug in the PyQtWebEngine bindings.
        """
        # notification id 0 means 'assign us the ID'. We can't just pass 0
        # because it won't get sent as the right type.
        notification_id = QVariant(0)
        notification_id.convert(QVariant.UInt)

        actions_list = QDBusArgument([], QMetaType.QStringList)

        qt_notification.show()
        hints = {
            # Include the origin in case the user wants to do different things
            # with different origin's notifications.
            "x-qutebrowser-origin": qt_notification.origin().toDisplayString()
        }  # type: typing.Dict[str, typing.Any]
        if not qt_notification.icon().isNull():
            hints["image-data"] = self._convert_image(qt_notification.icon())

        reply = self.interface.call(
            QDBus.BlockWithGui,
            "Notify",
            "qutebrowser",  # application name
            notification_id,
            "qutebrowser",  # icon
            qt_notification.title(),
            qt_notification.message(),
            actions_list,
            hints,
            -1,  # timeout; -1 means 'use default'
        )

        if reply.signature() != "u":
            raise DBusException(
                "Got an unexpected reply {}; expected a single uint32".format(reply.arguments())
            )

        notification_id = reply.arguments()[0]
        self._active_notifications[notification_id] = qt_notification
        log.webview.debug("Sent out notification {}".format(notification_id))

    def _convert_image(self, qimage: QImage) -> QDBusArgument:
        """Converts a QImage to the structure DBus expects."""
        # This is apparently what GTK-based notification daemons expect; tested it with dunst.
        # Otherwise you get weird color schemes.
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
            # WORKAROUND for https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042919.html
            # byteCount() is obsolete, but sizeInBytes() is only available with
            # SIP >= 5.3.0.
            size = qimage.byteCount()
        bits = qimage.constBits().asstring(size)
        image_data.add(QByteArray(bits))
        image_data.endStructure()
        return image_data

    @pyqtSlot(QDBusMessage)
    def _handle_close(self, message: QDBusMessage) -> None:
        notification_id = message.arguments()[0]
        if notification_id in self._active_notifications:
            try:
                self._active_notifications[notification_id].close()
            except RuntimeError:
                # WORKAROUND for https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
                pass
