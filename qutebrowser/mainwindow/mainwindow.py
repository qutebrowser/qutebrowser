# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""The main window of qutebrowser."""

import binascii
import base64
import itertools
import functools

import jinja2
from PyQt5.QtCore import pyqtSlot, QRect, QPoint, QTimer, Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QSizePolicy

from qutebrowser.commands import runners, cmdutils
from qutebrowser.config import config
from qutebrowser.utils import message, log, usertypes, qtutils, objreg, utils
from qutebrowser.mainwindow import tabbedbrowser, messageview, prompt
from qutebrowser.mainwindow.statusbar import bar
from qutebrowser.completion import completionwidget, completer
from qutebrowser.keyinput import modeman
from qutebrowser.browser import (commands, downloadview, hints,
                                 qtnetworkdownloads, downloads)
from qutebrowser.misc import crashsignal, keyhintwidget


win_id_gen = itertools.count(0)


def get_window(via_ipc, force_window=False, force_tab=False,
               force_target=None):
    """Helper function for app.py to get a window id.

    Args:
        via_ipc: Whether the request was made via IPC.
        force_window: Whether to force opening in a window.
        force_tab: Whether to force opening in a tab.
        force_target: Override the new-instance-open-target config
    """
    if force_window and force_tab:
        raise ValueError("force_window and force_tab are mutually exclusive!")

    if not via_ipc:
        # Initial main window
        return 0

    open_target = config.get('general', 'new-instance-open-target')

    # Apply any target overrides, ordered by precedence
    if force_target is not None:
        open_target = force_target
    if force_window:
        open_target = 'window'
    if force_tab and open_target == 'window':
        # Command sent via IPC
        open_target = 'tab-silent'

    window = None
    raise_window = False

    # Try to find the existing tab target if opening in a tab
    if open_target != 'window':
        window = get_target_window()
        raise_window = open_target not in ['tab-silent', 'tab-bg-silent']

    # Otherwise, or if no window was found, create a new one
    if window is None:
        window = MainWindow()
        window.show()
        raise_window = True

    if raise_window:
        window.setWindowState(window.windowState() & ~Qt.WindowMinimized)
        window.setWindowState(window.windowState() | Qt.WindowActive)
        window.raise_()
        window.activateWindow()
        QApplication.instance().alert(window)

    return window.win_id


def get_target_window():
    """Get the target window for new tabs, or None if none exist."""
    try:
        win_mode = config.get('general', 'new-instance-open-target.window')
        if win_mode == 'last-focused':
            return objreg.last_focused_window()
        elif win_mode == 'first-opened':
            return objreg.window_by_index(0)
        elif win_mode == 'last-opened':
            return objreg.window_by_index(-1)
        elif win_mode == 'last-visible':
            return objreg.last_visible_window()
        else:
            raise ValueError("Invalid win_mode {}".format(win_mode))
    except objreg.NoWindow:
        return None


class MainWindow(QWidget):

    """The main window of qutebrowser.

    Adds all needed components to a vbox, initializes sub-widgets and connects
    signals.

    Attributes:
        status: The StatusBar widget.
        tabbed_browser: The TabbedBrowser widget.
        _downloadview: The DownloadView widget.
        _vbox: The main QVBoxLayout.
        _commandrunner: The main CommandRunner instance.
        _overlays: Widgets shown as overlay for the current webpage.
    """

    def __init__(self, geometry=None, parent=None):
        """Create a new main window.

        Args:
            geometry: The geometry to load, as a bytes-object (or None).
            parent: The parent the window should get.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._commandrunner = None
        self._overlays = []
        self.win_id = next(win_id_gen)
        self.registry = objreg.ObjectRegistry()
        objreg.window_registry[self.win_id] = self
        objreg.register('main-window', self, scope='window',
                        window=self.win_id)
        tab_registry = objreg.ObjectRegistry()
        objreg.register('tab-registry', tab_registry, scope='window',
                        window=self.win_id)

        message_bridge = message.MessageBridge(self)
        objreg.register('message-bridge', message_bridge, scope='window',
                        window=self.win_id)

        self.setWindowTitle('qutebrowser')
        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(0)

        self._init_downloadmanager()
        self._downloadview = downloadview.DownloadView(self.win_id)

        self.tabbed_browser = tabbedbrowser.TabbedBrowser(self.win_id)
        objreg.register('tabbed-browser', self.tabbed_browser, scope='window',
                        window=self.win_id)
        self._init_command_dispatcher()

        # We need to set an explicit parent for StatusBar because it does some
        # show/hide magic immediately which would mean it'd show up as a
        # window.
        self.status = bar.StatusBar(self.win_id, parent=self)

        self._add_widgets()
        self._downloadview.show()

        self._init_completion()

        log.init.debug("Initializing modes...")
        modeman.init(self.win_id, self)

        self._commandrunner = runners.CommandRunner(self.win_id,
                                                    partial_match=True)

        self._keyhint = keyhintwidget.KeyHintView(self.win_id, self)
        self._add_overlay(self._keyhint, self._keyhint.update_geometry)
        self._messageview = messageview.MessageView(parent=self)
        self._add_overlay(self._messageview, self._messageview.update_geometry)

        self._prompt_container = prompt.PromptContainer(self.win_id, self)
        self._add_overlay(self._prompt_container,
                          self._prompt_container.update_geometry,
                          centered=True, padding=10)
        objreg.register('prompt-container', self._prompt_container,
                        scope='window', window=self.win_id)
        self._prompt_container.hide()

        if geometry is not None:
            self._load_geometry(geometry)
        elif self.win_id == 0:
            self._load_state_geometry()
        else:
            self._set_default_geometry()
        log.init.debug("Initial main window geometry: {}".format(
            self.geometry()))

        self._connect_signals()

        # When we're here the statusbar might not even really exist yet, so
        # resizing will fail. Therefore, we use singleShot QTimers to make sure
        # we defer this until everything else is initialized.
        QTimer.singleShot(0, self._connect_overlay_signals)
        objreg.get('config').changed.connect(self.on_config_changed)

        objreg.get("app").new_window.emit(self)

    def _add_overlay(self, widget, signal, *, centered=False, padding=0):
        self._overlays.append((widget, signal, centered, padding))

    def _update_overlay_geometries(self):
        """Update the size/position of all overlays."""
        for w, _signal, centered, padding in self._overlays:
            self._update_overlay_geometry(w, centered, padding)

    def _update_overlay_geometry(self, widget, centered, padding):
        """Reposition/resize the given overlay."""
        if not widget.isVisible():
            return

        size_hint = widget.sizeHint()
        if widget.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding:
            width = self.width() - 2 * padding
            left = padding
        else:
            width = min(size_hint.width(), self.width() - 2 * padding)
            left = (self.width() - width) / 2 if centered else 0

        height_padding = 20
        status_position = config.get('ui', 'status-position')
        if status_position == 'bottom':
            top = self.height() - self.status.height() - size_hint.height()
            top = qtutils.check_overflow(top, 'int', fatal=False)
            topleft = QPoint(left, max(height_padding, top))
            bottomright = QPoint(left + width, self.status.geometry().top())
        elif status_position == 'top':
            topleft = QPoint(left, self.status.geometry().bottom())
            bottom = self.status.height() + size_hint.height()
            bottom = qtutils.check_overflow(bottom, 'int', fatal=False)
            bottomright = QPoint(left + width,
                                 min(self.height() - height_padding, bottom))
        else:
            raise ValueError("Invalid position {}!".format(status_position))

        rect = QRect(topleft, bottomright)
        log.misc.debug('new geometry for {!r}: {}'.format(widget, rect))
        if rect.isValid():
            widget.setGeometry(rect)

    def _init_downloadmanager(self):
        log.init.debug("Initializing downloads...")
        qtnetwork_download_manager = qtnetworkdownloads.DownloadManager(
            self.win_id, self)
        objreg.register('qtnetwork-download-manager',
                        qtnetwork_download_manager,
                        scope='window', window=self.win_id)

        try:
            webengine_download_manager = objreg.get(
                'webengine-download-manager')
        except KeyError:
            webengine_download_manager = None

        download_model = downloads.DownloadModel(qtnetwork_download_manager,
                                                 webengine_download_manager)
        objreg.register('download-model', download_model, scope='window',
                        window=self.win_id)

    def _init_completion(self):
        self._completion = completionwidget.CompletionView(self.win_id, self)
        cmd = objreg.get('status-command', scope='window', window=self.win_id)
        completer_obj = completer.Completer(cmd, self.win_id, self._completion)
        self._completion.selection_changed.connect(
            completer_obj.on_selection_changed)
        objreg.register('completion', self._completion, scope='window',
                        window=self.win_id)
        self._add_overlay(self._completion, self._completion.update_geometry)

    def _init_command_dispatcher(self):
        dispatcher = commands.CommandDispatcher(self.win_id,
                                                self.tabbed_browser)
        objreg.register('command-dispatcher', dispatcher, scope='window',
                        window=self.win_id)
        self.tabbed_browser.destroyed.connect(
            functools.partial(objreg.delete, 'command-dispatcher',
                              scope='window', window=self.win_id))

    def __repr__(self):
        return utils.get_repr(self)

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Resize the completion if related config options changed."""
        if section != 'ui':
            return
        if option == 'statusbar-padding':
            self._update_overlay_geometries()
        elif option == 'downloads-position':
            self._add_widgets()
        elif option == 'status-position':
            self._add_widgets()
            self._update_overlay_geometries()

    def _add_widgets(self):
        """Add or readd all widgets to the VBox."""
        self._vbox.removeWidget(self.tabbed_browser)
        self._vbox.removeWidget(self._downloadview)
        self._vbox.removeWidget(self.status)
        downloads_position = config.get('ui', 'downloads-position')
        status_position = config.get('ui', 'status-position')
        widgets = [self.tabbed_browser]

        if downloads_position == 'top':
            widgets.insert(0, self._downloadview)
        elif downloads_position == 'bottom':
            widgets.append(self._downloadview)
        else:
            raise ValueError("Invalid position {}!".format(downloads_position))

        if status_position == 'top':
            widgets.insert(0, self.status)
        elif status_position == 'bottom':
            widgets.append(self.status)
        else:
            raise ValueError("Invalid position {}!".format(status_position))

        for widget in widgets:
            self._vbox.addWidget(widget)

    def _load_state_geometry(self):
        """Load the geometry from the state file."""
        state_config = objreg.get('state-config')
        try:
            data = state_config['geometry']['mainwindow']
            geom = base64.b64decode(data, validate=True)
        except KeyError:
            # First start
            self._set_default_geometry()
        except binascii.Error:
            log.init.exception("Error while reading geometry")
            self._set_default_geometry()
        else:
            self._load_geometry(geom)

    def _save_geometry(self):
        """Save the window geometry to the state config."""
        state_config = objreg.get('state-config')
        data = bytes(self.saveGeometry())
        geom = base64.b64encode(data).decode('ASCII')
        state_config['geometry']['mainwindow'] = geom

    def _load_geometry(self, geom):
        """Load geometry from a bytes object.

        If loading fails, loads default geometry.
        """
        log.init.debug("Loading mainwindow from {!r}".format(geom))
        ok = self.restoreGeometry(geom)
        if not ok:
            log.init.warning("Error while loading geometry.")
            self._set_default_geometry()

    def _connect_overlay_signals(self):
        """Connect the resize signal and resize everything once."""
        for widget, signal, centered, padding in self._overlays:
            signal.connect(
                functools.partial(self._update_overlay_geometry, widget,
                                  centered, padding))
            self._update_overlay_geometry(widget, centered, padding)

    def _set_default_geometry(self):
        """Set some sensible default geometry."""
        self.setGeometry(QRect(50, 50, 800, 600))

    def _get_object(self, name):
        """Get an object for this window in the object registry."""
        return objreg.get(name, scope='window', window=self.win_id)

    def _connect_signals(self):
        """Connect all mainwindow signals."""
        key_config = objreg.get('key-config')

        status = self._get_object('statusbar')
        keyparsers = self._get_object('keyparsers')
        completion_obj = self._get_object('completion')
        tabs = self._get_object('tabbed-browser')
        cmd = self._get_object('status-command')
        message_bridge = self._get_object('message-bridge')
        mode_manager = self._get_object('mode-manager')

        # misc
        self.tabbed_browser.close_window.connect(self.close)
        mode_manager.entered.connect(hints.on_mode_entered)

        # status bar
        mode_manager.entered.connect(status.on_mode_entered)
        mode_manager.left.connect(status.on_mode_left)
        mode_manager.left.connect(cmd.on_mode_left)
        mode_manager.left.connect(message.global_bridge.mode_left)

        # commands
        keyparsers[usertypes.KeyMode.normal].keystring_updated.connect(
            status.keystring.setText)
        cmd.got_cmd.connect(self._commandrunner.run_safely)
        cmd.returnPressed.connect(tabs.on_cmd_return_pressed)

        # key hint popup
        for mode, parser in keyparsers.items():
            parser.keystring_updated.connect(functools.partial(
                self._keyhint.update_keyhint, mode.name))

        # config
        for obj in keyparsers.values():
            key_config.changed.connect(obj.on_keyconfig_changed)

        # messages
        message.global_bridge.show_message.connect(
            self._messageview.show_message)

        message_bridge.s_set_text.connect(status.set_text)
        message_bridge.s_maybe_reset_text.connect(status.txt.maybe_reset_text)

        # statusbar
        tabs.current_tab_changed.connect(status.prog.on_tab_changed)
        tabs.cur_progress.connect(status.prog.setValue)
        tabs.cur_load_finished.connect(status.prog.hide)
        tabs.cur_load_started.connect(status.prog.on_load_started)

        tabs.current_tab_changed.connect(status.percentage.on_tab_changed)
        tabs.cur_scroll_perc_changed.connect(status.percentage.set_perc)

        tabs.tab_index_changed.connect(status.tabindex.on_tab_index_changed)

        tabs.current_tab_changed.connect(status.url.on_tab_changed)
        tabs.cur_url_changed.connect(status.url.set_url)
        tabs.cur_link_hovered.connect(status.url.set_hover_url)
        tabs.cur_load_status_changed.connect(status.url.on_load_status_changed)

        # command input / completion
        mode_manager.left.connect(tabs.on_mode_left)
        cmd.clear_completion_selection.connect(
            completion_obj.on_clear_completion_selection)
        cmd.hide_completion.connect(completion_obj.hide)

    @cmdutils.register(instance='main-window', scope='window')
    @pyqtSlot()
    def close(self):
        """Close the current window.

        //

        Extend close() so we can register it as a command.
        """
        super().close()

    @cmdutils.register(instance='main-window', scope='window')
    def fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def resizeEvent(self, e):
        """Extend resizewindow's resizeEvent to adjust completion.

        Args:
            e: The QResizeEvent
        """
        super().resizeEvent(e)
        self._update_overlay_geometries()
        self._downloadview.updateGeometry()
        self.tabbed_browser.tabBar().refresh()

    def showEvent(self, e):
        """Extend showEvent to register us as the last-visible-main-window.

        Args:
            e: The QShowEvent
        """
        super().showEvent(e)
        objreg.register('last-visible-main-window', self, update=True)

    def _do_close(self):
        """Helper function for closeEvent."""
        try:
            last_visible = objreg.get('last-visible-main-window')
            if self is last_visible:
                objreg.delete('last-visible-main-window')
        except KeyError:
            pass
        objreg.get('session-manager').save_last_window_session()
        self._save_geometry()
        log.destroy.debug("Closing window {}".format(self.win_id))
        self.tabbed_browser.shutdown()

    def closeEvent(self, e):
        """Override closeEvent to display a confirmation if needed."""
        if crashsignal.is_crashing:
            e.accept()
            return
        confirm_quit = config.get('ui', 'confirm-quit')
        tab_count = self.tabbed_browser.count()
        download_model = objreg.get('download-model', scope='window',
                                    window=self.win_id)
        download_count = download_model.running_downloads()
        quit_texts = []
        # Ask if multiple-tabs are open
        if 'multiple-tabs' in confirm_quit and tab_count > 1:
            quit_texts.append("{} {} open.".format(
                tab_count, "tab is" if tab_count == 1 else "tabs are"))
        # Ask if multiple downloads running
        if 'downloads' in confirm_quit and download_count > 0:
            quit_texts.append("{} {} running.".format(
                download_count,
                "download is" if download_count == 1 else "downloads are"))
        # Process all quit messages that user must confirm
        if quit_texts or 'always' in confirm_quit:
            msg = jinja2.Template("""
                <ul>
                {% for text in quit_texts %}
                   <li>{{text}}</li>
                {% endfor %}
                </ul>
            """.strip()).render(quit_texts=quit_texts)
            confirmed = message.ask('Really quit?', msg,
                                    mode=usertypes.PromptMode.yesno,
                                    default=True)

            # Stop asking if the user cancels
            if not confirmed:
                log.destroy.debug("Cancelling closing of window {}".format(
                    self.win_id))
                e.ignore()
                return
        e.accept()
        self._do_close()
