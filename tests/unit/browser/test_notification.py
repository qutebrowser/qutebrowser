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

import logging
import itertools
import inspect
from typing import List, Dict, Any, Optional, TYPE_CHECKING

import pytest
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QUrl, QObject
from PyQt5.QtGui import QImage
from PyQt5.QtDBus import QDBusMessage, QDBus, QDBusConnection
pytest.importorskip("PyQt5.QtWebEngineCore")
if TYPE_CHECKING:
    from PyQt5.QtWebEngineCore import QWebEngineNotification

from qutebrowser.config import configdata
from qutebrowser.misc import objects
from qutebrowser.browser.webengine import notification


pytestmark = [
    pytest.mark.qtwebengine_notifications,
    # 5.13 only supports the default presenter
    pytest.mark.skipif(not notification._notifications_supported(),
                       reason="Notifications not supported")
]


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


class FakeWebEngineNotification(QObject):

    closed = pyqtSignal()

    def origin(self) -> QUrl:
        return QUrl("https://example.org")

    def icon(self) -> QImage:
        return QImage()

    def title(self) -> str:
        return "notification title"

    def message(self) -> str:
        return "notification message"

    def tag(self) -> None:
        return None

    def show(self) -> None:
        pass


@pytest.fixture
def fake_notification():
    return FakeWebEngineNotification()


def _get_notification_adapters():
    return [value for _name, value in inspect.getmembers(notification, lambda obj: (
        inspect.isclass(obj) and
        issubclass(obj, notification.AbstractNotificationAdapter) and
        obj is not notification.AbstractNotificationAdapter
    ))]


@pytest.mark.parametrize("klass", _get_notification_adapters())
def test_name_attribute(klass, configdata_init):
    values = configdata.DATA["content.notifications.presenter"].typ.valid_values
    assert klass.NAME not in {"auto", "qt"}
    assert klass.NAME in values


class FakeNotificationAdapter(notification.AbstractNotificationAdapter):

    NAME = "fake"

    def __init__(self) -> None:
        super().__init__()
        self.presented = []
        self.id_gen = itertools.count(1)

    def present(
        self,
        qt_notification: "QWebEngineNotification", *,
        replaces_id: Optional[int],
    ) -> int:
        self.presented.append(qt_notification)
        return next(self.id_gen)

    @pyqtSlot(int)
    def on_web_closed(self, notification_id: int) -> None:
        """Called when a notification was closed by the website."""
        raise NotImplementedError


@pytest.mark.linux
class TestDBus:

    NO_REPLY_ERROR = FakeDBusMessage.create_error("org.freedesktop.DBus.Error.NoReply")
    FATAL_ERROR = FakeDBusMessage.create_error("test")

    @pytest.fixture
    def dbus_adapter_patches(self, monkeypatch, config_stub):
        monkeypatch.setattr(objects, "debug_flags", ["test-notification-service"])
        monkeypatch.setattr(notification, "QDBusInterface", FakeDBusInterface)

    @pytest.fixture
    def dbus_adapter(self, dbus_adapter_patches):
        return notification.DBusNotificationAdapter()

    @pytest.fixture
    def dbus_presenter(self, dbus_adapter_patches, monkeypatch):
        monkeypatch.setattr(
            notification.NotificationBridgePresenter,
            "_get_adapter_candidates",
            lambda _self, _setting: [
                notification.DBusNotificationAdapter,
                FakeNotificationAdapter,
            ],
        )
        return notification.NotificationBridgePresenter()

    def test_notify_fatal_error(self, dbus_adapter, fake_notification):
        dbus_adapter.interface.notify_reply = self.FATAL_ERROR
        with pytest.raises(notification.DBusError):
            dbus_adapter.present(fake_notification, replaces_id=None)

    def test_notify_fatal_error_presenter(self, dbus_presenter, fake_notification):
        dbus_presenter._init_adapter()
        dbus_presenter._adapter.interface.notify_reply = self.FATAL_ERROR
        with pytest.raises(notification.DBusError):
            dbus_presenter.present(fake_notification)

    def test_notify_non_fatal_error(self, qtbot, dbus_adapter, fake_notification):
        dbus_adapter.interface.notify_reply = self.NO_REPLY_ERROR
        with qtbot.wait_signal(dbus_adapter.error) as blocker:
            dbus_adapter.present(fake_notification, replaces_id=None)
        assert blocker.args == [f"error: {self.NO_REPLY_ERROR.errorName()}"]

    def test_notify_non_fatal_error_presenter(
        self,
        dbus_presenter,
        fake_notification,
        caplog,
    ):
        dbus_presenter._init_adapter()
        dbus_presenter._adapter.interface.notify_reply = self.NO_REPLY_ERROR

        with caplog.at_level(logging.ERROR):
            dbus_presenter.present(fake_notification)

        message = (
            'Notification error from libnotify adapter: '
            f'{self.NO_REPLY_ERROR.errorMessage()}'
        )
        assert message in caplog.messages
        assert dbus_presenter._adapter is None  # adapter dropped

    @pytest.mark.parametrize("error, exctype", [
        (NO_REPLY_ERROR, notification.DBusError),
        (FATAL_ERROR, notification.Error),
    ])
    def test_capabilities_error(
        self,
        dbus_adapter_patches,
        monkeypatch,
        error,
        exctype,
    ):
        monkeypatch.setattr(FakeDBusInterface, "CAPABILITIES_REPLY", error)
        with pytest.raises(exctype):
            notification.DBusNotificationAdapter()

    @pytest.mark.parametrize("error", [NO_REPLY_ERROR, FATAL_ERROR],
                             ids=lambda e: e.errorName())
    def test_capabilities_error_presenter(
        self,
        dbus_presenter,
        fake_notification,
        monkeypatch,
        caplog,
        error,
    ):
        monkeypatch.setattr(FakeDBusInterface, "CAPABILITIES_REPLY", error)
        dbus_presenter.present(fake_notification)
        message = (
            'Failed to initialize libnotify notification adapter: '
            f'{error.errorName()}: {error.errorMessage()}'
        )
        assert message in caplog.messages

        assert isinstance(dbus_presenter._adapter, FakeNotificationAdapter)
        assert dbus_presenter._adapter.presented == [fake_notification]
