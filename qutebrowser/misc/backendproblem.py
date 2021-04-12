# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2017-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Dialogs shown when there was a problem with a backend choice."""

import os
import sys
import functools
import html
import enum
import shutil
import argparse
import dataclasses
from typing import Any, List, Sequence, Tuple, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QPushButton, QHBoxLayout, QVBoxLayout, QLabel,
                             QMessageBox, QWidget)
from PyQt5.QtNetwork import QSslSocket

from qutebrowser.config import config, configfiles
from qutebrowser.utils import (usertypes, version, qtutils, log, utils,
                               standarddir)
from qutebrowser.misc import objects, msgbox, savemanager, quitter


class _Result(enum.IntEnum):

    """The result code returned by the backend problem dialog."""

    quit = QDialog.Accepted + 1
    restart = QDialog.Accepted + 2
    restart_webkit = QDialog.Accepted + 3
    restart_webengine = QDialog.Accepted + 4


@dataclasses.dataclass
class _Button:

    """A button passed to BackendProblemDialog."""

    text: str
    setting: str
    value: Any
    default: bool = False


def _other_backend(backend: usertypes.Backend) -> Tuple[usertypes.Backend, str]:
    """Get the other backend enum/setting for a given backend."""
    other_backend = {
        usertypes.Backend.QtWebKit: usertypes.Backend.QtWebEngine,
        usertypes.Backend.QtWebEngine: usertypes.Backend.QtWebKit,
    }[backend]
    other_setting = other_backend.name.lower()[2:]
    return (other_backend, other_setting)


def _error_text(because: str, text: str, backend: usertypes.Backend) -> str:
    """Get an error text for the given information."""
    other_backend, other_setting = _other_backend(backend)
    if other_backend == usertypes.Backend.QtWebKit:
        warning = ("<i>Note that QtWebKit hasn't been updated since "
                   "July 2017 (including security updates).</i>")
        suffix = " (not recommended)"
    else:
        warning = ""
        suffix = ""
    return ("<b>Failed to start with the {backend} backend!</b>"
            "<p>qutebrowser tried to start with the {backend} backend but "
            "failed because {because}.</p>{text}"
            "<p><b>Forcing the {other_backend.name} backend{suffix}</b></p>"
            "<p>This forces usage of the {other_backend.name} backend by "
            "setting the <i>backend = '{other_setting}'</i> option "
            "(if you have a <i>config.py</i> file, you'll need to set "
            "this manually). {warning}</p>".format(
                backend=backend.name, because=because, text=text,
                other_backend=other_backend, other_setting=other_setting,
                warning=warning, suffix=suffix))


class _Dialog(QDialog):

    """A dialog which gets shown if there are issues with the backend."""

    def __init__(self, *, because: str,
                 text: str,
                 backend: usertypes.Backend,
                 buttons: Sequence[_Button] = None,
                 parent: QWidget = None) -> None:
        super().__init__(parent)
        vbox = QVBoxLayout(self)

        other_backend, other_setting = _other_backend(backend)
        text = _error_text(because, text, backend)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        vbox.addWidget(label)

        hbox = QHBoxLayout()
        buttons = [] if buttons is None else buttons

        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(lambda: self.done(_Result.quit))
        hbox.addWidget(quit_button)

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

        if status in [_Result.quit, QDialog.Rejected]:
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

    def _xwayland_options(self) -> Tuple[str, List[_Button]]:
        """Get buttons/text for a possible XWayland solution."""
        buttons = []
        text = "<p>You can work around this in one of the following ways:</p>"

        if 'DISPLAY' in os.environ:
            # XWayland is available, but QT_QPA_PLATFORM=wayland is set
            buttons.append(
                _Button("Force XWayland", 'qt.force_platform', 'xcb'))
            text += ("<p><b>Force Qt to use XWayland</b></p>"
                     "<p>This allows you to use the newer QtWebEngine backend "
                     "(based on Chromium). "
                     "This sets the <i>qt.force_platform = 'xcb'</i> option "
                     "(if you have a <i>config.py</i> file, you'll need to "
                     "set this manually).</p>")
        else:
            text += ("<p><b>Set up XWayland</b></p>"
                     "<p>This allows you to use the newer QtWebEngine backend "
                     "(based on Chromium). ")

        return text, buttons

    def _handle_wayland_webgl(self) -> None:
        """On older graphic hardware, WebGL on Wayland causes segfaults.

        See https://github.com/qutebrowser/qutebrowser/issues/5313
        """
        self._assert_backend(usertypes.Backend.QtWebEngine)

        if os.environ.get('QUTE_SKIP_WAYLAND_WEBGL_CHECK'):
            return

        platform = objects.qapp.platformName()
        if platform not in ['wayland', 'wayland-egl']:
            return

        # Only Qt 5.14 should be affected
        if not qtutils.version_check('5.14', compiled=False):
            return
        if qtutils.version_check('5.15', compiled=False):
            return

        # Newer graphic hardware isn't affected
        opengl_info = version.opengl_info()
        if (opengl_info is None or
                opengl_info.gles or
                opengl_info.version is None or
                opengl_info.version >= (4, 3)):
            return

        # If WebGL is turned off, we're fine
        if not config.val.content.webgl:
            return

        text, buttons = self._xwayland_options()

        buttons.append(_Button("Turn off WebGL (recommended)",
                               'content.webgl',
                               False))
        text += ("<p><b>Disable WebGL (recommended)</b></p>"
                 "This sets the <i>content.webgl = False</i> option "
                 "(if you have a <i>config.py</i> file, you'll need to "
                 "set this manually).</p>")

        self._show_dialog(backend=usertypes.Backend.QtWebEngine,
                          because=("of frequent crashes with Qt 5.14 on "
                                   "Wayland with older graphics hardware"),
                          text=text,
                          buttons=buttons)

    def _try_import_backends(self) -> _BackendImports:
        """Check whether backends can be imported and return BackendImports."""
        # pylint: disable=unused-import
        results = _BackendImports()

        try:
            from PyQt5 import QtWebKit
            from PyQt5.QtWebKit import qWebKitVersion
            from PyQt5 import QtWebKitWidgets
        except (ImportError, ValueError) as e:
            results.webkit_error = str(e)
        else:
            if not qtutils.is_new_qtwebkit():
                results.webkit_error = "Unsupported legacy QtWebKit found"

        try:
            from PyQt5 import QtWebEngineWidgets
        except (ImportError, ValueError) as e:
            results.webengine_error = str(e)

        return results

    def _handle_ssl_support(self, fatal: bool = False) -> None:
        """Check for full SSL availability.

        If "fatal" is given, show an error and exit.
        """
        if QSslSocket.supportsSsl():
            return

        if qtutils.version_check('5.12.4'):
            version_text = ("If you use OpenSSL 1.0 with a PyQt package from "
                            "PyPI (e.g. on Ubuntu 16.04), you will need to "
                            "build OpenSSL 1.1 from sources and set "
                            "LD_LIBRARY_PATH accordingly.")
        else:
            version_text = ("If you use OpenSSL 1.1 with a PyQt package from "
                            "PyPI (e.g. on Archlinux or Debian Stretch), you "
                            "need to set LD_LIBRARY_PATH to the path of "
                            "OpenSSL 1.0 or use Qt >= 5.12.4.")

        text = ("Could not initialize QtNetwork SSL support. {} This only "
                "affects downloads and :adblock-update.".format(version_text))

        if fatal:
            errbox = msgbox.msgbox(parent=None,
                                   title="SSL error",
                                   text="Could not initialize SSL support.",
                                   icon=QMessageBox.Critical,
                                   plain_text=False)
            errbox.exec()
            sys.exit(usertypes.Exit.err_init)

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
                    "</ul></p>".format(
                        webkit_error=html.escape(imports.webkit_error),
                        webengine_error=html.escape(imports.webengine_error)))
            errbox = msgbox.msgbox(parent=None,
                                   title="No backend library found!",
                                   text=text,
                                   icon=QMessageBox.Critical,
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

    def _handle_cache_nuking(self) -> None:
        """Nuke the QtWebEngine cache if the Qt version changed.

        WORKAROUND for https://bugreports.qt.io/browse/QTBUG-72532
        """
        if not configfiles.state.qt_version_changed:
            return

        # Only nuke the cache in cases where we know there are problems.
        # It seems these issues started with Qt 5.12.
        # They should be fixed with Qt 5.12.5:
        # https://codereview.qt-project.org/c/qt/qtwebengine-chromium/+/265408
        if qtutils.version_check('5.12.5', compiled=False):
            return

        log.init.info("Qt version changed, nuking QtWebEngine cache")
        cache_dir = os.path.join(standarddir.cache(), 'webengine')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)

    def _handle_serviceworker_nuking(self) -> None:
        """Nuke the service workers directory if the Qt version changed.

        WORKAROUND for:
        https://bugreports.qt.io/browse/QTBUG-72532
        https://bugreports.qt.io/browse/QTBUG-82105
        """
        if ('serviceworker_workaround' not in configfiles.state['general'] and
                qtutils.version_check('5.14', compiled=False)):
            # Nuke the service worker directory once for every install with Qt
            # 5.14, given that it seems to cause a variety of segfaults.
            configfiles.state['general']['serviceworker_workaround'] = '514'
            reason = 'Qt 5.14'
        elif configfiles.state.qt_version_changed:
            reason = 'Qt version changed'
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

    def _assert_backend(self, backend: usertypes.Backend) -> None:
        assert objects.backend == backend, objects.backend

    def check(self) -> None:
        """Run all checks."""
        self._check_backend_modules()
        if objects.backend == usertypes.Backend.QtWebEngine:
            self._handle_ssl_support()
            self._handle_wayland_webgl()
            self._handle_cache_nuking()
            self._handle_serviceworker_nuking()
        else:
            self._assert_backend(usertypes.Backend.QtWebKit)
            self._handle_ssl_support(fatal=True)


def init(*, args: argparse.Namespace,
         save_manager: savemanager.SaveManager) -> None:
    """Run all checks."""
    checker = _BackendProblemChecker(no_err_windows=args.no_err_windows,
                                     save_manager=save_manager)
    checker.check()
