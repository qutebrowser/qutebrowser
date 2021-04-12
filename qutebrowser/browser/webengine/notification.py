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

"""Different ways of showing notifications to the user.

Our notification implementation consists of two different parts:

- NotificationBridgePresenter, the object we set as notification presenter on
  QWebEngineProfiles on startup.
- Adapters (subclassing from AbstractNotificationAdapter) which get called by the bridge
  and contain the code to show notifications using different means (e.g. a systray icon
  or DBus).

Adapters are initialized lazily when the bridge gets the first notification. This makes
sure we don't block while e.g. talking to DBus during startup, but only when needed.

If an adapter raises Error during __init__, the bridge assumes that it's unavailable and
tries the next one in a list of candidates.

Useful test pages:

- https://tests.peter.sh/notification-generator/
- https://www.bennish.net/web-notifications.html
- https://web-push-book.gauntface.com/demos/notification-examples/
- tests/end2end/data/javascript/notifications.html
"""

import os
import signal
import html
import dataclasses
import itertools
import functools
import subprocess
from typing import Any, List, Dict, Optional, Iterator, TYPE_CHECKING

from PyQt5.QtCore import (Qt, QObject, QVariant, QMetaType, QByteArray, pyqtSlot,
                          pyqtSignal, QTimer, QProcess, QUrl)
from PyQt5.QtGui import QImage, QIcon, QPixmap
from PyQt5.QtDBus import (QDBusConnection, QDBusInterface, QDBus, QDBusServiceWatcher,
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
    if not qtutils.version_check('5.14'):
        return

    global bridge
    bridge = NotificationBridgePresenter()


class Error(Exception):
    """Raised when something goes wrong with notifications."""


class AbstractNotificationAdapter(QObject):

    """An adapter taking notifications and displaying them.

    This can happen via different mechanisms, e.g. a system tray icon or DBus.
    """

    # A short name for the adapter, shown in errors. Should be the same as the
    # associated content.notification.presenter setting.
    NAME: str

    # Emitted by the adapter when the notification with the given ID was closed or
    # clicked by the user.
    close_id = pyqtSignal(int)
    click_id = pyqtSignal(int)

    # Emitted by the adapter when an error occurred, which should result in the adapter
    # getting swapped out (potentially initializing the same adapter again, or using a
    # different one if that fails).
    error = pyqtSignal(str)
    clear_all = pyqtSignal()

    def present(
        self,
        qt_notification: "QWebEngineNotification",
        *,
        replaces_id: Optional[int],
    ) -> int:
        """Show the given notification.

        If replaces_id is given, replace the currently showing notification with the
        same ID.

        Returns an ID assigned to the new notifications. IDs must be positive (>= 1) and
        must not duplicate any active notification's ID.
        """
        raise NotImplementedError

    def _should_include_origin(self, origin: QUrl) -> bool:
        """Check if the origin is useful to include.

        If we open the page via a file scheme, the origin is QUrl('file:///') which
        doesn't help much.
        """
        return bool(
            origin.host() and
            config.instance.get('content.notifications.show_origin', url=origin),
        )

    @pyqtSlot(int)
    def on_web_closed(self, notification_id: int) -> None:
        """Called when a notification was closed by the website."""
        raise NotImplementedError


class NotificationBridgePresenter(QObject):

    """Notification presenter which bridges notifications to an adapter.

    Takes care of:
    - Working around bugs in PyQt 5.14
    - Storing currently shown notifications, using an ID returned by the adapter.
    - Initializing a suitable adapter when the first notification is shown.
    - Switching out adapters if the current one emitted its error signal.
    """

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        assert qtutils.version_check('5.14')

        self._active_notifications: Dict[int, 'QWebEngineNotification'] = {}
        self._adapter: Optional[AbstractNotificationAdapter] = None

        config.instance.changed.connect(self._init_adapter)

    @config.change_filter('content.notifications.presenter')
    def _init_adapter(self) -> None:
        """Initialize the adapter to use based on the config."""
        setting = config.val.content.notifications.presenter
        log.misc.debug(f"Setting up notification adapter ({setting})...")

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
        elif setting == "herbe":
            candidates = [
                HerbeNotificationAdapter,
                DBusNotificationAdapter,
                SystrayNotificationAdapter,
                MessagesNotificationAdapter,
            ]
        elif setting == "messages":
            candidates = [MessagesNotificationAdapter]  # always succeeds
        else:
            raise utils.Unreachable(setting)

        for candidate in candidates:
            try:
                self._adapter = candidate()
            except Error as e:
                msg = f"Failed to initialize {candidate.NAME} notification adapter: {e}"
                if candidate.NAME == setting:  # We picked this one explicitly
                    message.error(msg)
                else:  # automatic fallback
                    log.misc.debug(msg)
            else:
                log.misc.debug(f"Initialized {self._adapter.NAME} notification adapter")
                break

        assert self._adapter is not None
        self._adapter.click_id.connect(self._on_adapter_clicked)
        self._adapter.close_id.connect(self._on_adapter_closed)
        self._adapter.error.connect(self._on_adapter_error)
        self._adapter.clear_all.connect(self._on_adapter_clear_all)

    def install(self, profile: "QWebEngineProfile") -> None:
        """Set the profile to use this bridge as the presenter."""
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
        """Show a notification using the configured adapter.

        Lazily initializes a suitable adapter if none exists yet.

        This should *not* be directly passed to setNotificationPresenter on
        PyQtWebEngine < 5.15 because of a bug in the PyQtWebEngine bindings.
        """
        if self._adapter is None:
            self._init_adapter()
            assert self._adapter is not None

        replaces_id = self._find_replaces_id(qt_notification)
        qtutils.ensure_valid(qt_notification.origin())

        notification_id = self._adapter.present(
            qt_notification, replaces_id=replaces_id)
        log.misc.debug(f"New notification ID from adapter: {notification_id}")

        if self._adapter is None:
            # If a fatal error occurred, we replace the adapter via its "error" signal.
            log.misc.debug("Adapter vanished, bailing out")  # type: ignore[unreachable]
            return

        if notification_id <= 0:
            raise Error(f"Got invalid notification id {notification_id}")

        if replaces_id is None:
            if notification_id in self._active_notifications:
                raise Error(f"Got duplicate id {notification_id}")

        qt_notification.show()
        self._active_notifications[notification_id] = qt_notification

        qt_notification.closed.connect(  # type: ignore[attr-defined]
            functools.partial(self._adapter.on_web_closed, notification_id))

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

        log.misc.debug(
            f"Finding notification for tag {new_notification.tag()}, "
            f"origin {new_notification.origin()}")

        try:
            for notification_id, notification in sorted(
                    self._active_notifications.items(), reverse=True):
                if notification.matches(new_notification):
                    log.misc.debug(f"Found match: {notification_id}")
                    return notification_id
        except RuntimeError:
            # WORKAROUND for
            # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
            # (also affects .matches)
            log.misc.debug(
                f"Ignoring notification tag {new_notification.tag()!r} due to PyQt bug")

        log.misc.debug("Did not find match")
        return None

    @pyqtSlot(int)
    def _on_adapter_closed(self, notification_id: int) -> None:
        """A notification was closed by the adapter (usually due to the user).

        Accepts unknown notification IDs, as this can be called for notifications from
        other applications (with the DBus adapter).
        """
        log.misc.debug(f"Notification {notification_id} closed by adapter")

        try:
            notification = self._active_notifications.pop(notification_id)
        except KeyError:
            log.misc.debug("Did not find matching notification, ignoring")
            # Notification from a different application
            return

        try:
            notification.close()
        except RuntimeError:
            # WORKAROUND for
            # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
            log.misc.debug(f"Ignoring close request for notification {notification_id} "
                           "due to PyQt bug")

    @pyqtSlot(int)
    def _on_adapter_clicked(self, notification_id: int) -> None:
        """A notification was clicked by the adapter (usually due to the user).

        Accepts unknown notification IDs, as this can be called for notifications from
        other applications (with the DBus adapter).
        """
        log.misc.debug(f"Notification {notification_id} clicked by adapter")

        try:
            notification = self._active_notifications[notification_id]
        except KeyError:
            # Notification from a different application
            log.misc.debug("Did not find matching notification, ignoring")
            return

        try:
            notification.click()
        except RuntimeError:
            # WORKAROUND for
            # https://www.riverbankcomputing.com/pipermail/pyqt/2020-May/042918.html
            log.misc.debug(f"Ignoring click request for notification {notification_id} "
                           "due to PyQt bug")

    def _drop_adapter(self) -> None:
        """Drop the currently active adapter (if any).

        This means we'll reinitialize a new one (including re-testing available options)
        on the next notification.
        """
        if self._adapter:
            log.misc.debug(f"Dropping adapter {self._adapter.NAME}")
            self._adapter.deleteLater()

        self._adapter = None
        self._on_adapter_clear_all()

    @pyqtSlot()
    def _on_adapter_clear_all(self) -> None:
        """Called when the adapter requests clearing all notifications.

        This is currently only done if the DBus notification server was unregistered.
        It's probably safe to assume no notifications exist anymore. Also, this makes
        sure we don't have any duplicate IDs.

        Depending on the system, either the server will automatically be restarted on
        the next notification, or we'll get a (properly handled) NoReply error then.
        """
        for notification_id in list(self._active_notifications):
            self._on_adapter_closed(notification_id)

    @pyqtSlot(str)
    def _on_adapter_error(self, error: str) -> None:
        """A fatal error happened in the adapter.

        This causes us to drop the current adapter and reinit it (or a different one) on
        the next notification.
        """
        if self._adapter is None:
            # Error during setup
            return

        log.misc.error(
            f"Notification error from {self._adapter.NAME} adapter: {error}")
        self._drop_adapter()


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
    NOTIFICATION_ID = 1  # only one concurrent notification supported

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
        msg = self._format_message(qt_notification.message(), qt_notification.origin())

        self._systray.showMessage(qt_notification.title(), msg, icon)

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

    def _format_message(self, text: str, origin: QUrl) -> str:
        """Format the message to display."""
        if not self._should_include_origin(origin):
            return text
        return origin.toDisplayString() + '\n\n' + text

    @pyqtSlot()
    def _on_systray_clicked(self) -> None:
        self.click_id.emit(self.NOTIFICATION_ID)

    @pyqtSlot(int)
    def on_web_closed(self, notification_id: int) -> None:
        assert notification_id == self.NOTIFICATION_ID, notification_id
        self._systray.hide()


class MessagesNotificationAdapter(AbstractNotificationAdapter):

    """Shows notifications using qutebrowser messages.

    This is mostly used as a fallback if no other method is available. Most notification
    features are not supported.

    Note that it's expected for this adapter to never fail (i.e. not raise Error in
    __init__ and not emit the error signal), as it's used as a "last resort" fallback.
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
        markup = self._format_message(qt_notification)
        new_id = replaces_id if replaces_id is not None else next(self._id_gen)

        message.info(markup, replace=f'notifications-{new_id}')

        # Faking closing, timing might not be 100% accurate
        QTimer.singleShot(
            config.val.messages.timeout, lambda: self.close_id.emit(new_id))

        return new_id

    @pyqtSlot(int)
    def on_web_closed(self, _notification_id: int) -> None:
        """We can't close messages."""

    def _format_message(self, qt_notification: "QWebEngineNotification") -> str:
        title = html.escape(qt_notification.title())
        body = html.escape(qt_notification.message())
        hint = "" if qt_notification.icon().isNull() else " (image not shown)"

        if self._should_include_origin(qt_notification.origin()):
            url = html.escape(qt_notification.origin().toDisplayString())
            origin_str = f" from {url}"
        else:
            origin_str = ""

        return (
            f"<i>Notification{origin_str}:{hint}</i><br/><br/>"
            f"<b>{title}</b><br/>"
            f"{body}"
        )


class HerbeNotificationAdapter(AbstractNotificationAdapter):

    """Shows notifications using herbe.

    See https://github.com/dudik/herbe
    """

    NAME = "herbe"

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        # Also cleans up potentially hanging semaphores from herbe.
        # https://github.com/dudik/herbe#notifications-dont-show-up
        try:
            subprocess.run(['herbe'], stderr=subprocess.DEVNULL, check=True)
        except OSError as e:
            raise Error(f'herbe error: {e}')
        except subprocess.CalledProcessError as e:
            if e.returncode != 1:
                raise Error(f'herbe exited with status {e.returncode}')

    def present(
        self,
        qt_notification: "QWebEngineNotification",
        *,
        replaces_id: Optional[int],
    ) -> int:
        if replaces_id is not None:
            self.on_web_closed(replaces_id)

        proc = QProcess(self)
        proc.errorOccurred.connect(self._on_error)

        lines = list(self._message_lines(qt_notification))
        proc.start('herbe', lines)

        pid = proc.processId()
        assert pid > 1
        proc.finished.connect(functools.partial(self._on_finished, pid))

        return pid

    def _message_lines(
        self,
        qt_notification: "QWebEngineNotification",
    ) -> Iterator[str]:
        """Get the lines to display for this notification."""
        yield qt_notification.title()

        origin = qt_notification.origin()
        if self._should_include_origin(origin):
            yield origin.toDisplayString()

        yield qt_notification.message()

        if not qt_notification.icon().isNull():
            yield "(icon not shown)"

    def _on_finished(self, pid: int, code: int, status: QProcess.ExitStatus) -> None:
        """Handle a closing herbe process.

        From the GitHub page:
        - "An accepted notification always returns exit code 0."
        - "Dismissed notifications return exit code 2."

        Any other exit status should never happen.

        We ignore CrashExit as SIGUSR1/SIGUSR2 are expected "crashes", and for any other
        signals, we can't do much - emitting self.error would just go use herbe again,
        so there's no point.
        """
        if status == QProcess.CrashExit:
            return

        if code == 0:
            self.click_id.emit(pid)
        elif code == 2:
            self.close_id.emit(pid)
        else:
            proc = self.sender()
            stderr = proc.readAllStandardError()
            raise Error(f'herbe exited with status {code}: {stderr}')

    @pyqtSlot(QProcess.ProcessError)
    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.Crashed:
            return
        name = debug.qenum_key(QProcess.ProcessError, error)
        raise Error(f'herbe process error: {name}')

    @pyqtSlot(int)
    def on_web_closed(self, notification_id: int) -> None:
        """Handle closing the notification from JS.

        From herbe's README:
        "A notification can be dismissed [...] [by] sending a SIGUSR1 signal to it"
        """
        os.kill(notification_id, signal.SIGUSR1)
        # Make sure we immediately remove it from active notifications
        self.close_id.emit(notification_id)


@dataclasses.dataclass
class _ServerQuirks:

    """Quirks for certain DBus notification servers."""

    spec_version: Optional[str] = None
    avoid_actions: bool = False
    avoid_body_hyperlinks: bool = False
    escape_title: bool = False
    icon_key: Optional[str] = None
    skip_capabilities: bool = False
    wrong_replaces_id: bool = False
    no_padded_images: bool = False


@dataclasses.dataclass
class _ServerCapabilities:

    """Notification capabilities supported by the server."""

    actions: bool
    body_markup: bool
    body_hyperlinks: bool
    kde_origin_name: bool

    @classmethod
    def from_list(cls, capabilities: List[str]) -> "_ServerCapabilities":
        return cls(
            actions='actions' in capabilities,
            body_markup='body-markup' in capabilities,
            body_hyperlinks='body-hyperlinks' in capabilities,
            kde_origin_name='x-kde-origin-name' in capabilities,
        )


def _as_uint32(x: int) -> QVariant:
    """Convert the given int to an uint32 for DBus."""
    variant = QVariant(x)
    assert variant.convert(QVariant.UInt)
    return variant


class DBusNotificationAdapter(AbstractNotificationAdapter):

    """Send notifications over DBus.

    This is essentially what libnotify does, except using Qt's DBus implementation.

    Related specs:
    https://developer.gnome.org/notification-spec/
    https://specifications.freedesktop.org/notification-spec/notification-spec-latest.html
    https://wiki.ubuntu.com/NotificationDevelopmentGuidelines
    """

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

        self._watcher = QDBusServiceWatcher(
            self.SERVICE,
            bus,
            QDBusServiceWatcher.WatchForUnregistration,
            self,
        )
        self._watcher.serviceUnregistered.connect(  # type: ignore[attr-defined]
            self._on_service_unregistered)

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

        if self._quirks.skip_capabilities:
            self._capabilities = _ServerCapabilities.from_list([])
        else:
            self._fetch_capabilities()

    @pyqtSlot(str)
    def _on_service_unregistered(self) -> None:
        """Make sure we know when the notification daemon exits.

        If that's the case, we bail out, as otherwise notifications would fail or the
        next start of the server would lead to duplicate notification IDs.
        """
        log.misc.debug("Notification daemon did quit!")
        self.clear_all.emit()

    def _find_quirks(  # noqa: C901 ("too complex"
        self,
        name: str,
        vendor: str,
        version: str,
    ) -> Optional[_ServerQuirks]:
        """Find quirks to use based on the server information."""
        if (name, vendor) == ("notify-osd", "Canonical Ltd"):
            # Shows a dialog box instead of a notification bubble as soon as a
            # notification has an action (even if only a default one). Dialog boxes are
            # buggy and return a notification with ID 0.
            # https://wiki.ubuntu.com/NotificationDevelopmentGuidelines#Avoiding_actions
            return _ServerQuirks(avoid_actions=True, spec_version="1.1")
        elif (name, vendor) == ("Notification Daemon", "MATE"):
            # Still in active development but doesn't implement spec 1.2:
            # https://github.com/mate-desktop/mate-notification-daemon/issues/132
            quirks = _ServerQuirks(spec_version="1.1")
            if utils.VersionNumber.parse(version) <= utils.VersionNumber(1, 24):
                # https://github.com/mate-desktop/mate-notification-daemon/issues/118
                quirks.avoid_body_hyperlinks = True
            return quirks
        elif (name, vendor) == ("naughty", "awesome"):
            # Still in active development but spec 1.0/1.2 support isn't
            # released yet:
            # https://github.com/awesomeWM/awesome/commit/e076bc664e0764a3d3a0164dabd9b58d334355f4
            parsed_version = utils.VersionNumber.parse(version.lstrip('v'))
            if parsed_version <= utils.VersionNumber(4, 3):
                return _ServerQuirks(spec_version="1.0")
        elif (name, vendor) == ("twmnd", "twmnd"):
            # https://github.com/sboli/twmn/pull/96
            return _ServerQuirks(spec_version="0")
        elif (name, vendor) == ("tiramisu", "Sweets"):
            # https://github.com/Sweets/tiramisu/issues/20
            return _ServerQuirks(skip_capabilities=True)
        elif (name, vendor) == ("lxqt-notificationd", "lxqt.org"):
            quirks = _ServerQuirks()
            parsed_version = utils.VersionNumber.parse(version)
            if parsed_version <= utils.VersionNumber(0, 16):
                # https://github.com/lxqt/lxqt-notificationd/issues/253
                quirks.escape_title = True
            if parsed_version < utils.VersionNumber(0, 16):
                # https://github.com/lxqt/lxqt-notificationd/commit/c23e254a63c39837fb69d5c59c5e2bc91e83df8c
                quirks.icon_key = 'image_data'
            return quirks
        elif (name, vendor) == ("haskell-notification-daemon", "abc"):  # aka "deadd"
            return _ServerQuirks(
                # https://github.com/phuhl/linux_notification_center/issues/160
                spec_version="1.0",
                # https://github.com/phuhl/linux_notification_center/issues/161
                wrong_replaces_id=True,
            )
        elif (name, vendor) == ("ninomiya", "deifactor"):
            return _ServerQuirks(
                no_padded_images=True,
                wrong_replaces_id=True,
            )
        elif (name, vendor) == ("Raven", "Budgie Desktop Developers"):
            return _ServerQuirks(
                # https://github.com/solus-project/budgie-desktop/issues/2114
                escape_title=True,
                # https://github.com/solus-project/budgie-desktop/issues/2115
                wrong_replaces_id=True,
            )
        return None

    def _get_server_info(self) -> None:
        """Query notification server information and set quirks."""
        reply = self.interface.call(QDBus.BlockWithGui, "GetServerInformation")
        self._verify_message(reply, "ssss", QDBusMessage.ReplyMessage)
        name, vendor, version, spec_version = reply.arguments()

        log.misc.debug(
            f"Connected to notification server: {name} {version} by {vendor}, "
            f"implementing spec {spec_version}")

        quirks = self._find_quirks(name, vendor, version)
        if quirks is not None:
            log.misc.debug(f"Enabling quirks {quirks}")
            self._quirks = quirks

        expected_spec_version = self._quirks.spec_version or self.SPEC_VERSION
        if spec_version != expected_spec_version:
            log.misc.warning(
                f"Notification server ({name} {version} by {vendor}) implements "
                f"spec {spec_version}, but {expected_spec_version} was expected. "
                f"If {name} is up to date, please report a qutebrowser bug.")

        # https://specifications.freedesktop.org/notification-spec/latest/ar01s08.html
        icon_key_overrides = {
            "1.0": "icon_data",
            "1.1": "image_data",
        }
        if spec_version in icon_key_overrides:
            self._quirks.icon_key = icon_key_overrides[spec_version]

    def _dbus_error_str(self, error: QDBusError) -> str:
        """Get a string for a DBus error."""
        if not error.isValid():
            return "Unknown error"
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
            err = msg.errorName()
            if err == "org.freedesktop.DBus.Error.NoReply":
                self.error.emit(msg.errorMessage())  # notification daemon is gone
                return

            raise Error(f"Got DBus error: {err} - {msg.errorMessage()}")

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
        if replaces_id is None:
            replaces_id = 0  # 0 is never a valid ID according to the spec

        actions = []
        if self._capabilities.actions:
            actions = ['default', 'Activate']  # key, name
        actions_arg = QDBusArgument(actions, QMetaType.QStringList)

        origin_url_str = qt_notification.origin().toDisplayString()
        hints: Dict[str, Any] = {
            # Include the origin in case the user wants to do different things
            # with different origin's notifications.
            "x-qutebrowser-origin": origin_url_str,
            "desktop-entry": "org.qutebrowser.qutebrowser",
        }

        is_useful_origin = self._should_include_origin(qt_notification.origin())
        if self._capabilities.kde_origin_name and is_useful_origin:
            hints["x-kde-origin-name"] = origin_url_str

        icon = qt_notification.icon()
        if icon.isNull():
            filename = ':/icons/qutebrowser-64x64.png'
            icon = QImage(filename)

        key = self._quirks.icon_key or "image-data"
        data = self._convert_image(icon)
        if data is not None:
            hints[key] = data

        # Titles don't support markup (except with broken servers)
        title = qt_notification.title()
        if self._quirks.escape_title:
            title = html.escape(title, quote=False)

        reply = self.interface.call(
            QDBus.BlockWithGui,
            "Notify",
            "qutebrowser",  # application name
            _as_uint32(replaces_id),  # replaces notification id
            "",  # icon name/file URL, we use image-data and friends instead.
            title,
            self._format_body(qt_notification.message(), qt_notification.origin()),
            actions_arg,
            hints,
            -1,  # timeout; -1 means 'use default'
        )
        self._verify_message(reply, "u", QDBusMessage.ReplyMessage)

        notification_id = reply.arguments()[0]

        if replaces_id not in [0, notification_id]:
            msg = (
                f"Wanted to replace notification {replaces_id} but got new id "
                f"{notification_id}."
            )
            if self._quirks.wrong_replaces_id:
                log.misc.debug(msg)
            else:
                log.misc.error(msg)

        return notification_id

    def _convert_image(self, qimage: QImage) -> Optional[QDBusArgument]:
        """Convert a QImage to the structure DBus expects.

        https://specifications.freedesktop.org/notification-spec/latest/ar01s05.html#icons-and-images-formats
        """
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
        assert 0 <= padding <= 3, (padding, bytes_per_line, width, channel_count)
        size -= padding

        if padding and self._quirks.no_padded_images:
            return None

        bits = qimage.constBits().asstring(size)
        image_data.add(QByteArray(bits))

        image_data.endStructure()
        return image_data

    @pyqtSlot(QDBusMessage)
    def _handle_close(self, msg: QDBusMessage) -> None:
        """Handle NotificationClosed from DBus."""
        self._verify_message(msg, "uu", QDBusMessage.SignalMessage)
        notification_id, _close_reason = msg.arguments()
        self.close_id.emit(notification_id)

    @pyqtSlot(QDBusMessage)
    def _handle_action(self, msg: QDBusMessage) -> None:
        """Handle ActionInvoked from DBus."""
        self._verify_message(msg, "us", QDBusMessage.SignalMessage)
        notification_id, action_key = msg.arguments()
        if action_key == "default":
            self.click_id.emit(notification_id)

    @pyqtSlot(int)
    def on_web_closed(self, notification_id: int) -> None:
        """Send CloseNotification if a notification was closed from JS."""
        self.interface.call(
            QDBus.NoBlock,
            "CloseNotification",
            _as_uint32(notification_id),
        )

    def _fetch_capabilities(self) -> None:
        """Fetch capabilities from the notification server."""
        reply = self.interface.call(
            QDBus.BlockWithGui,
            "GetCapabilities",
        )
        self._verify_message(reply, "as", QDBusMessage.ReplyMessage)

        caplist = reply.arguments()[0]
        self._capabilities = _ServerCapabilities.from_list(caplist)
        if self._quirks.avoid_actions:
            self._capabilities.actions = False
        if self._quirks.avoid_body_hyperlinks:
            self._capabilities.body_hyperlinks = False

        log.misc.debug(f"Notification server capabilities: {self._capabilities}")

    def _format_body(self, body: str, origin_url: QUrl) -> str:
        """Format the body according to the server capabilities.

        If the server doesn't support x-kde-origin-name, we include the origin URL as a
        prefix. If possible, we hyperlink it.

        For both prefix and body, we'll need to HTML escape it if the server supports
        body markup.
        """
        urlstr = origin_url.toDisplayString()
        is_useful_origin = self._should_include_origin(origin_url)

        if self._capabilities.kde_origin_name or not is_useful_origin:
            prefix = None
        elif self._capabilities.body_markup and self._capabilities.body_hyperlinks:
            href = html.escape(
                origin_url.toString(QUrl.FullyEncoded)  # type: ignore[arg-type]
            )
            text = html.escape(urlstr, quote=False)
            prefix = f'<a href="{href}">{text}</a>'
        elif self._capabilities.body_markup:
            prefix = html.escape(urlstr, quote=False)
        else:
            prefix = urlstr

        if self._capabilities.body_markup:
            body = html.escape(body, quote=False)

        if prefix is None:
            return body

        return prefix + '\n\n' + body
