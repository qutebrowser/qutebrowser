# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Dialogs shown when there was a problem with a backend choice."""

import os
import sys
import functools
import html
import enum
import shutil
import os.path
import argparse
import dataclasses
from typing import Any, Optional
from collections.abc import Sequence

from qutebrowser.qt import machinery
from qutebrowser.qt.core import Qt
from qutebrowser.qt.widgets import (QDialog, QPushButton, QHBoxLayout, QVBoxLayout, QLabel,
                             QMessageBox, QWidget)
from qutebrowser.qt.network import QSslSocket

from qutebrowser.config import config, configfiles
from qutebrowser.utils import (usertypes, version, qtutils, log, utils,
                               standarddir)
from qutebrowser.misc import objects, msgbox, savemanager, quitter


class _Result(enum.IntEnum):

    """The result code returned by the backend problem dialog."""

    quit = QDialog.DialogCode.Accepted + 1
    restart = QDialog.DialogCode.Accepted + 2
    restart_webkit = QDialog.DialogCode.Accepted + 3
    restart_webengine = QDialog.DialogCode.Accepted + 4


@dataclasses.dataclass
class _Button:

    """A button passed to BackendProblemDialog."""

    text: str
    setting: str
    value: Any
    default: bool = False


def _other_backend(backend: usertypes.Backend) -> tuple[usertypes.Backend, str]:
    """Get the other backend enum/setting for a given backend."""
    other_backend = {
        usertypes.Backend.QtWebKit: usertypes.Backend.QtWebEngine,
        usertypes.Backend.QtWebEngine: usertypes.Backend.QtWebKit,
    }[backend]
    other_setting = other_backend.name.lower()[2:]
    return (other_backend, other_setting)


def _error_text(
    because: str,
    text: str,
    backend: usertypes.Backend,
    suggest_other_backend: bool = False,
) -> str:
    """Get an error text for the given information."""
    text = (f"<b>Failed to start with the {backend.name} backend!</b>"
            f"<p>qutebrowser tried to start with the {backend.name} backend but "
            f"failed because {because}.</p>{text}")

    if suggest_other_backend:
        other_backend, other_setting = _other_backend(backend)
        if other_backend == usertypes.Backend.QtWebKit:
            warning = ("<i>Note that QtWebKit hasn't been updated since "
                    "July 2017 (including security updates).</i>")
            suffix = " (not recommended)"
        else:
            warning = ""
            suffix = ""

        text += (f"<p><b>Forcing the {other_backend.name} backend{suffix}</b></p>"
                 f"<p>This forces usage of the {other_backend.name} backend by "
                 f"setting the <i>backend = '{other_setting}'</i> option "
                 f"(if you have a <i>config.py</i> file, you'll need to set "
                 f"this manually). {warning}</p>")

    text += f"<p>{machinery.INFO.to_html()}</p>"
    return text


class _Dialog(QDialog):

    """A dialog which gets shown if there are issues with the backend."""

    def __init__(self, *, because: str,
                 text: str,
                 backend: usertypes.Backend,
                 suggest_other_backend: bool = True,
                 buttons: Sequence[_Button] = None,
                 parent: QWidget = None) -> None:
        super().__init__(parent)
        vbox = QVBoxLayout(self)

        text = _error_text(because, text, backend,
                           suggest_other_backend=suggest_other_backend)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        vbox.addWidget(label)

        hbox = QHBoxLayout()
        buttons = [] if buttons is None else buttons

        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(lambda: self.done(_Result.quit))
        hbox.addWidget(quit_button)

        if suggest_other_backend:
            other_backend, other_setting = _other_backend(backend)
            backend_text = "Force {} backend".format(other_backend.name)
            if other_backend == usertypes.Backend.QtWebKit:
                backend_text += ' (not recommended)'
            backend_button = QPushButton(backend_text)
            backend_button.clicked.connect(functools.partial(
                self._change_setting, 'backend', other_setting))
            hbox.addWidget(backend_button)

        for button in buttons:
            btn = QPushButton(button.text)
            btn.setDefault(button.default)
            btn.clicked.connect(functools.partial(
                self._change_setting, button.setting, button.value))
            hbox.addWidget(btn)

        vbox.addLayout(hbox)

    def _change_setting(self, setting: str, value: str) -> None:
        """Change the given setting and restart."""
        config.instance.set_obj(setting, value, save_yaml=True)

        if setting == 'backend' and value == 'webkit':
            self.done(_Result.restart_webkit)
        elif setting == 'backend' and value == 'webengine':
            self.done(_Result.restart_webengine)
        else:
            self.done(_Result.restart)


@dataclasses.dataclass
class _BackendImports:

    """Whether backend modules could be imported."""

    webkit_error: Optional[str] = None
    webengine_error: Optional[str] = None


class _BackendProblemChecker:

    """Check for various backend-specific issues."""

    def __init__(self, *,
                 no_err_windows: bool,
                 save_manager: savemanager.SaveManager) -> None:
        self._save_manager = save_manager
        self._no_err_windows = no_err_windows

    def _show_dialog(self, *args: Any, **kwargs: Any) -> None:
        """Show a dialog for a backend problem."""
        if self._no_err_windows:
            text = _error_text(*args, **kwargs)
            log.init.error(text)
            sys.exit(usertypes.Exit.err_init)

        dialog = _Dialog(*args, **kwargs)

        status = dialog.exec()
        self._save_manager.save_all(is_exit=True)

        if status in [_Result.quit, QDialog.DialogCode.Rejected]:
            pass
        elif status == _Result.restart_webkit:
            quitter.instance.restart(override_args={'backend': 'webkit'})
        elif status == _Result.restart_webengine:
            quitter.instance.restart(override_args={'backend': 'webengine'})
        elif status == _Result.restart:
            quitter.instance.restart()
        else:
            raise utils.Unreachable(status)

        sys.exit(usertypes.Exit.err_init)

    def _try_import_backends(self) -> _BackendImports:
        """Check whether backends can be imported and return BackendImports."""
        # pylint: disable=unused-import
        results = _BackendImports()

        try:
            from qutebrowser.qt import webkit, webkitwidgets
        except (ImportError, ValueError) as e:
            results.webkit_error = str(e)
            assert results.webkit_error
        else:
            if not qtutils.is_new_qtwebkit():
                results.webkit_error = "Unsupported legacy QtWebKit found"

        try:
            from qutebrowser.qt import webenginecore, webenginewidgets
        except (ImportError, ValueError) as e:
            results.webengine_error = str(e)
            assert results.webengine_error

        return results

    def _handle_ssl_support(self, fatal: bool = False) -> None:
        """Check for full SSL availability.

        If "fatal" is given, show an error and exit.
        """
        if QSslSocket.supportsSsl():
            return

        text = ("Could not initialize QtNetwork SSL support. This only "
                "affects downloads and :adblock-update.")

        if fatal:
            errbox = msgbox.msgbox(parent=None,
                                   title="SSL error",
                                   text="Could not initialize SSL support.",
                                   icon=QMessageBox.Icon.Critical,
                                   plain_text=False)
            errbox.exec()
            sys.exit(usertypes.Exit.err_init)

        # Doing this here because it's not relevant with QtWebKit where fatal=True
        if machinery.IS_QT6:
            text += ("\nHint: If installed via mkvenv.py on a system without "
                     "OpenSSL 3.x (e.g. Ubuntu 20.04), you can use --pyqt-version 6.4 "
                     "to get an older Qt still compatible with OpenSSL 1.1 (at the "
                     "expense of running an older QtWebEngine/Chromium)")

        assert not fatal
        log.init.warning(text)

    def _check_backend_modules(self) -> None:
        """Check for the modules needed for QtWebKit/QtWebEngine."""
        imports = self._try_import_backends()

        if not imports.webkit_error and not imports.webengine_error:
            return
        elif imports.webkit_error and imports.webengine_error:
            text = ("<p>qutebrowser needs QtWebKit or QtWebEngine, but "
                    "neither could be imported!</p>"
                    "<p>The errors encountered were:<ul>"
                    "<li><b>QtWebKit:</b> {webkit_error}"
                    "<li><b>QtWebEngine:</b> {webengine_error}"
                    "</ul></p><p>{info}</p>".format(
                        webkit_error=html.escape(imports.webkit_error),
                        webengine_error=html.escape(imports.webengine_error),
                        info=machinery.INFO.to_html(),
                    ))
            errbox = msgbox.msgbox(parent=None,
                                   title="No backend library found!",
                                   text=text,
                                   icon=QMessageBox.Icon.Critical,
                                   plain_text=False)
            errbox.exec()
            sys.exit(usertypes.Exit.err_init)
        elif objects.backend == usertypes.Backend.QtWebKit:
            if not imports.webkit_error:
                return
            self._show_dialog(
                backend=usertypes.Backend.QtWebKit,
                because="QtWebKit could not be imported",
                text="<p><b>The error encountered was:</b><br/>{}</p>".format(
                    html.escape(imports.webkit_error))
            )
        elif objects.backend == usertypes.Backend.QtWebEngine:
            if not imports.webengine_error:
                return
            self._show_dialog(
                backend=usertypes.Backend.QtWebEngine,
                because="QtWebEngine could not be imported",
                text="<p><b>The error encountered was:</b><br/>{}</p>".format(
                    html.escape(imports.webengine_error))
            )

        raise utils.Unreachable

    def _handle_serviceworker_nuking(self) -> None:
        """Nuke the service workers directory if the Qt version changed.

        WORKAROUND for:
        https://bugreports.qt.io/browse/QTBUG-72532
        https://bugreports.qt.io/browse/QTBUG-82105
        https://bugreports.qt.io/browse/QTBUG-93744
        """
        if configfiles.state.qt_version_changed:
            reason = 'Qt version changed'
        elif configfiles.state.qtwe_version_changed:
            reason = 'QtWebEngine version changed'
        elif config.val.qt.workarounds.remove_service_workers:
            reason = 'Explicitly enabled'
        else:
            return

        service_worker_dir = os.path.join(
            standarddir.data(), 'webengine', 'Service Worker')
        bak_dir = service_worker_dir + '-bak'
        if not os.path.exists(service_worker_dir):
            return

        log.init.info(
            f"Removing service workers at {service_worker_dir} (reason: {reason})")

        # Keep one backup around - we're not 100% sure what persistent data
        # could be in there, but this folder can grow to ~300 MB.
        if os.path.exists(bak_dir):
            shutil.rmtree(bak_dir)

        shutil.move(service_worker_dir, bak_dir)

    def _confirm_chromium_version_changes(self) -> None:
        """Ask if there are Chromium downgrades or a Qt 5 -> 6 upgrade."""
        versions = version.qtwebengine_versions(avoid_init=True)
        change = configfiles.state.chromium_version_changed
        info = f"<br><br>{machinery.INFO.to_html()}"
        if machinery.INFO.reason == machinery.SelectionReason.auto:
            info += (
                "<br><br>"
                "You can use <tt>--qt-wrapper</tt> or set <tt>QUTE_QT_WRAPPER</tt> "
                "in your environment to override this."
            )
        webengine_data_dir = os.path.join(standarddir.data(), "webengine")

        if change == configfiles.VersionChange.major:
            icon = QMessageBox.Icon.Information
            text = (
                "Chromium/QtWebEngine upgrade detected:<br>"
                f"You are <b>upgrading to QtWebEngine {versions.webengine}</b> but "
                "used Qt 5 for the last qutebrowser launch.<br><br>"
                "Data managed by Chromium will be upgraded. This is a <b>one-way "
                "operation:</b> If you open qutebrowser with Qt 5 again later, any "
                "Chromium data will be <b>invalid and discarded</b>.<br><br>"
                "This affects page data such as cookies, but not data managed by "
                "qutebrowser, such as your configuration or <tt>:open</tt> history.<br>"
                f"The affected data is in <tt>{webengine_data_dir}</tt>."
            ) + info
        elif change == configfiles.VersionChange.downgrade:
            icon = QMessageBox.Icon.Warning
            text = (
                "Chromium/QtWebEngine downgrade detected:<br>"
                f"You are <b>downgrading to QtWebEngine {versions.webengine}</b>."
                "<br><br>"
                "Data managed by Chromium <b>will be discarded</b> if you continue."
                "<br><br>"
                "This affects page data such as cookies, but not data managed by "
                "qutebrowser, such as your configuration or <tt>:open</tt> history.<br>"
                f"The affected data is in <tt>{webengine_data_dir}</tt>."
            ) + info
        else:
            return

        box = msgbox.msgbox(
            parent=None,
            title="QtWebEngine version change",
            text=text,
            icon=icon,
            plain_text=False,
            buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Abort,
        )
        response = box.exec()
        if response != QMessageBox.StandardButton.Ok:
            sys.exit(usertypes.Exit.err_init)

    def _check_webengine_version(self) -> None:
        versions = version.qtwebengine_versions(avoid_init=True)
        if versions.webengine < utils.VersionNumber(5, 15, 2):
            text = (
                "QtWebEngine >= 5.15.2 is required for qutebrowser, but "
                f"{versions.webengine} is installed.")
            errbox = msgbox.msgbox(parent=None,
                                   title="QtWebEngine too old",
                                   text=text,
                                   icon=QMessageBox.Icon.Critical,
                                   plain_text=False)
            errbox.exec()
            sys.exit(usertypes.Exit.err_init)

    def _check_software_rendering(self) -> None:
        """Avoid crashing software rendering settings.

        WORKAROUND for https://bugreports.qt.io/browse/QTBUG-103372
        Fixed with QtWebEngine 6.3.1.
        """
        self._assert_backend(usertypes.Backend.QtWebEngine)
        versions = version.qtwebengine_versions(avoid_init=True)

        if versions.webengine != utils.VersionNumber(6, 3):
            return

        if os.environ.get('QT_QUICK_BACKEND') != 'software':
            return

        text = ("You can instead force software rendering on the Chromium level (sets "
                "<tt>qt.force_software_rendering</tt> to <tt>chromium</tt> instead of "
                "<tt>qt-quick</tt>).")

        button = _Button("Force Chromium software rendering",
                         'qt.force_software_rendering',
                         'chromium')
        self._show_dialog(
            backend=usertypes.Backend.QtWebEngine,
            suggest_other_backend=False,
            because="a Qt 6.3.0 bug causes instant crashes with Qt Quick software rendering",
            text=text,
            buttons=[button],
        )

        raise utils.Unreachable

    def _assert_backend(self, backend: usertypes.Backend) -> None:
        assert objects.backend == backend, objects.backend

    def check(self) -> None:
        """Run all checks."""
        self._check_backend_modules()
        if objects.backend == usertypes.Backend.QtWebEngine:
            self._check_webengine_version()
            self._handle_ssl_support()
            self._handle_serviceworker_nuking()
            self._check_software_rendering()
            self._confirm_chromium_version_changes()
        else:
            self._assert_backend(usertypes.Backend.QtWebKit)
            self._handle_ssl_support(fatal=True)


def init(*, args: argparse.Namespace,
         save_manager: savemanager.SaveManager) -> None:
    """Run all checks."""
    checker = _BackendProblemChecker(no_err_windows=args.no_err_windows,
                                     save_manager=save_manager)
    checker.check()
