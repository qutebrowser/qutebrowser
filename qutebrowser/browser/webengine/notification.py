# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
from typing import Any, List, Dict, Optional, Iterator, Type, TYPE_CHECKING

from qutebrowser.qt import machinery
from qutebrowser.qt.core import (Qt, QObject, QVariant, QMetaType, QByteArray, pyqtSlot,
                          pyqtSignal, QTimer, QProcess, QUrl)
from qutebrowser.qt.gui import QImage, QIcon, QPixmap
from qutebrowser.qt.dbus import (QDBusConnection, QDBusInterface, QDBus, QDBusServiceWatcher,
                          QDBusArgument, QDBusMessage, QDBusError)
from qutebrowser.qt.widgets import QSystemTrayIcon

if TYPE_CHECKING:
    # putting these behind TYPE_CHECKING also means this module is importable
    # on installs that don't have these
    from qutebrowser.qt.webenginecore import QWebEngineNotification, QWebEngineProfile

from qutebrowser.config import config
from qutebrowser.misc import objects
from qutebrowser.utils import (
    qtutils, log, utils, debug, message, objreg, resources, urlutils
)
from qutebrowser.qt import sip


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


class DBusError(Error):
    """Raised when there was an error coming from DBus."""

    _NON_FATAL_ERRORS = {
        # notification daemon is gone
        "org.freedesktop.DBus.Error.NoReply",

        # https://gitlab.gnome.org/GNOME/gnome-flashback/-/blob/3.40.0/gnome-flashback/libnotifications/nd-daemon.c#L178-187
        # Exceeded maximum number of notifications
        "org.freedesktop.Notifications.MaxNotificationsExceeded",

        # https://bugs.kde.org/show_bug.cgi?id=409157
        # https://github.com/KDE/plasma-workspace/blob/v5.21.4/libnotificationmanager/server_p.cpp#L227-L237
        # Created too many similar notifications in quick succession
        "org.freedesktop.Notifications.Error.ExcessNotificationGeneration",

        # From https://crashes.qutebrowser.org/view/b8c9838a
        # Process org.freedesktop.Notifications received signal 5
        # probably when notification daemon crashes?
        "org.freedesktop.DBus.Error.Spawn.ChildSignaled",

        # https://crashes.qutebrowser.org/view/f76f58ae
        # Process org.freedesktop.Notifications exited with status 1
        "org.freedesktop.DBus.Error.Spawn.ChildExited",

        # https://crashes.qutebrowser.org/view/8889d0b5
        # Could not activate remote peer.
        "org.freedesktop.DBus.Error.NameHasNoOwner",

        # https://crashes.qutebrowser.org/view/de62220a
        # after "Notification daemon did quit!"
        "org.freedesktop.DBus.Error.UnknownObject",

        # notmuch-sha1-ef7b6e9e79e5f2f6cba90224122288895c1fe0d8
        "org.freedesktop.DBus.Error.ServiceUnknown",
    }

    def __init__(self, msg: QDBusMessage) -> None:
        assert msg.type() == QDBusMessage.MessageType.ErrorMessage
        self.error = msg.errorName()
        self.error_message = msg.errorMessage()
        self.is_fatal = self.error not in self._NON_FATAL_ERRORS
        text = f"{self.error}: {self.error_message}"
        super().__init__(text)


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
    - Storing currently shown notifications, using an ID returned by the adapter.
    - Initializing a suitable adapter when the first notification is shown.
    - Switching out adapters if the current one emitted its error signal.
    """

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)

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

        for candidate in self._get_adapter_candidates(setting):
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

    def _get_adapter_candidates(
        self,
        setting: str,
    ) -> List[Type[AbstractNotificationAdapter]]:
        candidates: Dict[str, List[Type[AbstractNotificationAdapter]]] = {
            "libnotify": [
                DBusNotificationAdapter,
                SystrayNotificationAdapter,
                MessagesNotificationAdapter,
            ],
            "systray": [
                SystrayNotificationAdapter,
                DBusNotificationAdapter,
                MessagesNotificationAdapter,
            ],
            "herbe": [
                HerbeNotificationAdapter,
                DBusNotificationAdapter,
                SystrayNotificationAdapter,
                MessagesNotificationAdapter,
            ],
            "messages": [MessagesNotificationAdapter],  # always succeeds
        }
        candidates["auto"] = candidates["libnotify"]
        return candidates[setting]

    def install(self, profile: "QWebEngineProfile") -> None:
        """Set the profile to use this bridge as the presenter."""
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

        if replaces_id is None:
            if notification_id in self._active_notifications:
                raise Error(f"Got duplicate id {notification_id}")

        qt_notification.show()
        self._active_notifications[notification_id] = qt_notification

        qt_notification.closed.connect(
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

        for notification_id, notification in sorted(
                self._active_notifications.items(), reverse=True):
            if notification.matches(new_notification):
                log.misc.debug(f"Found match: {notification_id}")
                return notification_id

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

        notification.close()

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

        notification.click()
        self._focus_first_matching_tab(notification)

    def _focus_first_matching_tab(self, notification: "QWebEngineNotification") -> None:
        for win_id in objreg.window_registry:
            tabbedbrowser = objreg.get("tabbed-browser", window=win_id, scope="window")
            for idx, tab in enumerate(tabbedbrowser.widgets()):
                if tab.url().matches(notification.origin(), QUrl.UrlFormattingOption.RemovePath):
                    tabbedbrowser.widget.setCurrentIndex(idx)
                    return
        log.misc.debug(f"No matching tab found for {notification.origin()}")

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

        message.error(f"Notification error from {self._adapter.NAME} adapter: {error}")
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
        pixmap = QPixmap.fromImage(image, Qt.ImageConversionFlag.NoFormatConversion)
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
        if not sip.isdeleted(self._systray):
            # This can get called during shutdown
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

        message.info(markup, replace=f'notifications-{new_id}', rich=True)

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
        if status == QProcess.ExitStatus.CrashExit:
            pass
        elif code == 0:
            self.click_id.emit(pid)
        elif code == 2:
            pass
        else:
            proc = self.sender()
            assert isinstance(proc, QProcess), proc
            stderr = proc.readAllStandardError()
            raise Error(f'herbe exited with status {code}: {stderr}')

        self.close_id.emit(pid)

    @pyqtSlot(QProcess.ProcessError)
    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.Crashed:
            return
        name = debug.qenum_key(QProcess, error)
        self.error.emit(f'herbe process error: {name}')

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
    wrong_closes_type: bool = False


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

    if machinery.IS_QT5:
        target = QVariant.Type.UInt
    else:  # Qt 6
        # FIXME:mypy PyQt6-stubs issue
        target = QMetaType(QMetaType.Type.UInt.value)  # type: ignore[call-overload]

    successful = variant.convert(target)
    assert successful
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
        super().__init__(parent)

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
            QDBusServiceWatcher.WatchModeFlag.WatchForUnregistration,
            self,
        )
        self._watcher.serviceUnregistered.connect(self._on_service_unregistered)

        test_service = 'test-notification-service' in objects.debug_flags
        service = f"{self.TEST_SERVICE}{os.getpid()}" if test_service else self.SERVICE

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
        ver: str,
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
            if utils.VersionNumber.parse(ver) <= utils.VersionNumber(1, 24):
                # https://github.com/mate-desktop/mate-notification-daemon/issues/118
                quirks.avoid_body_hyperlinks = True
            return quirks
        elif (name, vendor) == ("naughty", "awesome") and ver != "devel":
            # Still in active development but spec 1.0/1.2 support isn't
            # released yet:
            # https://github.com/awesomeWM/awesome/commit/e076bc664e0764a3d3a0164dabd9b58d334355f4
            parsed_version = utils.VersionNumber.parse(ver.lstrip('v'))
            if parsed_version <= utils.VersionNumber(4, 3):
                return _ServerQuirks(spec_version="1.0")
        elif (name, vendor) == ("twmnd", "twmnd"):
            # https://github.com/sboli/twmn/pull/96
            return _ServerQuirks(spec_version="0")
        elif (name, vendor) == ("tiramisu", "Sweets"):
            if utils.VersionNumber.parse(ver) < utils.VersionNumber(2):
                # https://github.com/Sweets/tiramisu/issues/20
                return _ServerQuirks(skip_capabilities=True)
        elif (name, vendor) == ("lxqt-notificationd", "lxqt.org"):
            quirks = _ServerQuirks()
            parsed_version = utils.VersionNumber.parse(ver)
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
            # Before refactor
            return _ServerQuirks(
                # https://github.com/solus-project/budgie-desktop/issues/2114
                escape_title=True,
                # https://github.com/solus-project/budgie-desktop/issues/2115
                wrong_replaces_id=True,
            )
        elif (name, vendor) == (
                "Budgie Notification Server", "Budgie Desktop Developers"):
            # After refactor: https://github.com/BuddiesOfBudgie/budgie-desktop/pull/36
            if utils.VersionNumber.parse(ver) < utils.VersionNumber(10, 6, 2):
                return _ServerQuirks(
                    # https://github.com/BuddiesOfBudgie/budgie-desktop/issues/118
                    wrong_closes_type=True,
                )
        return None

    def _get_server_info(self) -> None:
        """Query notification server information and set quirks."""
        reply = self.interface.call(QDBus.CallMode.BlockWithGui, "GetServerInformation")
        self._verify_message(reply, "ssss", QDBusMessage.MessageType.ReplyMessage)
        name, vendor, ver, spec_version = reply.arguments()

        log.misc.debug(
            f"Connected to notification server: {name} {ver} by {vendor}, "
            f"implementing spec {spec_version}")

        quirks = self._find_quirks(name, vendor, ver)
        if quirks is not None:
            log.misc.debug(f"Enabling quirks {quirks}")
            self._quirks = quirks

        expected_spec_versions = [self.SPEC_VERSION]
        if self._quirks.spec_version is not None:
            expected_spec_versions.append(self._quirks.spec_version)

        if spec_version not in expected_spec_versions:
            log.misc.warning(
                f"Notification server ({name} {ver} by {vendor}) implements "
                f"spec {spec_version}, but {'/'.join(expected_spec_versions)} was "
                f"expected. If {name} is up to date, please report a qutebrowser bug.")

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
            QDBusMessage.MessageType.ErrorMessage,
            QDBusMessage.MessageType.InvalidMessage,
        ], expected_type

        if msg.type() == QDBusMessage.MessageType.ErrorMessage:
            raise DBusError(msg)

        signature = msg.signature()
        if signature != expected_signature:
            raise Error(
                f"Got a message with signature {signature} but expected "
                f"{expected_signature} (args: {msg.arguments()})")

        typ = msg.type()
        if typ != expected_type:
            type_str = debug.qenum_key(QDBusMessage, typ)
            expected_type_str = debug.qenum_key(QDBusMessage, expected_type)
            raise Error(
                f"Got a message of type {type_str} but expected {expected_type_str}"
                f"(args: {msg.arguments()})")

    def _verify_notification_id(
        self,
        notification_id: int, *,
        replaces_id: int,
    ) -> None:
        """Ensure the returned notification id is valid."""
        if replaces_id not in [0, notification_id]:
            msg = (
                f"Wanted to replace notification {replaces_id} but got new id "
                f"{notification_id}."
            )
            if self._quirks.wrong_replaces_id:
                log.misc.debug(msg)
            else:
                log.misc.error(msg)

        if notification_id <= 0:
            self.error.emit(f"Got invalid notification id {notification_id}")

    def _get_title_arg(self, title: str) -> str:
        """Get the title argument for present()."""
        # Titles don't support markup (except with broken servers)
        if self._quirks.escape_title:
            return html.escape(title, quote=False)
        return title

    def _get_actions_arg(self) -> QDBusArgument:
        """Get the actions argument for present()."""
        actions = []
        if self._capabilities.actions:
            actions = ['default', 'Activate']  # key, name
        return QDBusArgument(
            actions,
            qtutils.extract_enum_val(QMetaType.Type.QStringList),
        )

    def _get_hints_arg(self, *, origin_url: QUrl, icon: QImage) -> Dict[str, Any]:
        """Get the hints argument for present()."""
        origin_url_str = origin_url.toDisplayString()
        hints: Dict[str, Any] = {
            # Include the origin in case the user wants to do different things
            # with different origin's notifications.
            "x-qutebrowser-origin": origin_url_str,
            "desktop-entry": "org.qutebrowser.qutebrowser",
        }

        is_useful_origin = self._should_include_origin(origin_url)
        if self._capabilities.kde_origin_name and is_useful_origin:
            hints["x-kde-origin-name"] = origin_url_str

        if icon.isNull():
            filename = 'icons/qutebrowser-64x64.png'
            icon = QImage.fromData(resources.read_file_binary(filename))

        key = self._quirks.icon_key or "image-data"
        data = self._convert_image(icon)
        if data is not None:
            hints[key] = data

        return hints

    def _call_notify_wrapper(
        self, *,
        appname: str,
        replaces_id: QVariant,
        icon: str,
        title: str,
        body: str,
        actions: QDBusArgument,
        hints: Dict[str, Any],
        timeout: int,
    ) -> Any:
        """Wrapper around DBus call to use keyword args."""
        return self.interface.call(
            QDBus.CallMode.BlockWithGui,
            "Notify",
            appname,
            replaces_id,
            icon,
            title,
            body,
            actions,
            hints,
            timeout,
        )

    def present(
        self,
        qt_notification: "QWebEngineNotification",
        *,
        replaces_id: Optional[int],
    ) -> int:
        """Shows a notification over DBus."""
        if replaces_id is None:
            replaces_id = 0  # 0 is never a valid ID according to the spec

        reply = self._call_notify_wrapper(
            appname="qutebrowser",
            replaces_id=_as_uint32(replaces_id),
            icon="",  # we use image-data and friends instead
            title=self._get_title_arg(qt_notification.title()),
            body=self._format_body(
                body=qt_notification.message(),
                origin_url=qt_notification.origin(),
            ),
            actions=self._get_actions_arg(),
            hints=self._get_hints_arg(
                origin_url=qt_notification.origin(),
                icon=qt_notification.icon(),
            ),
            timeout=-1,  # use default
        )

        try:
            self._verify_message(reply, "u", QDBusMessage.MessageType.ReplyMessage)
        except DBusError as e:
            if e.is_fatal:
                raise
            self.error.emit(e.error_message)
            # Return value gets ignored in NotificationBridgePresenter.present
            return -1

        notification_id = reply.arguments()[0]
        self._verify_notification_id(notification_id, replaces_id=replaces_id)
        return notification_id

    def _convert_image(self, qimage: QImage) -> Optional[QDBusArgument]:
        """Convert a QImage to the structure DBus expects.

        https://specifications.freedesktop.org/notification-spec/latest/ar01s05.html#icons-and-images-formats
        """
        bits_per_color = 8
        has_alpha = qimage.hasAlphaChannel()
        if has_alpha:
            image_format = QImage.Format.Format_RGBA8888
            channel_count = 4
        else:
            image_format = QImage.Format.Format_RGB888
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

        size = qimage.sizeInBytes()

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

        bits_ptr = qimage.constBits()
        assert bits_ptr is not None
        bits = bits_ptr.asstring(size)
        image_data.add(QByteArray(bits))

        image_data.endStructure()
        return image_data

    @pyqtSlot(QDBusMessage)
    def _handle_close(self, msg: QDBusMessage) -> None:
        """Handle NotificationClosed from DBus."""
        try:
            self._verify_message(msg, "uu", QDBusMessage.MessageType.SignalMessage)
        except Error:
            if not self._quirks.wrong_closes_type:
                raise
            self._verify_message(msg, "ui", QDBusMessage.MessageType.SignalMessage)

        notification_id, _close_reason = msg.arguments()
        self.close_id.emit(notification_id)

    @pyqtSlot(QDBusMessage)
    def _handle_action(self, msg: QDBusMessage) -> None:
        """Handle ActionInvoked from DBus."""
        self._verify_message(msg, "us", QDBusMessage.MessageType.SignalMessage)
        notification_id, action_key = msg.arguments()
        if action_key == "default":
            self.click_id.emit(notification_id)

    @pyqtSlot(int)
    def on_web_closed(self, notification_id: int) -> None:
        """Send CloseNotification if a notification was closed from JS."""
        self.interface.call(
            QDBus.CallMode.NoBlock,
            "CloseNotification",
            _as_uint32(notification_id),
        )

    def _fetch_capabilities(self) -> None:
        """Fetch capabilities from the notification server."""
        reply = self.interface.call(
            QDBus.CallMode.BlockWithGui,
            "GetCapabilities",
        )
        self._verify_message(reply, "as", QDBusMessage.MessageType.ReplyMessage)

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
            href = html.escape(origin_url.toString(urlutils.FormatOption.ENCODED))
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
