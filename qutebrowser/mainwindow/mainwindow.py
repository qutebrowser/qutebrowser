# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import typing

from PyQt5.QtCore import (pyqtSignal, pyqtSlot, QRect, QPoint, QTimer, Qt,
                          QCoreApplication, QEventLoop)
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication, QSizePolicy

from qutebrowser.commands import runners
from qutebrowser.api import cmdutils
from qutebrowser.config import config, configfiles, stylesheet
from qutebrowser.utils import (message, log, usertypes, qtutils, objreg, utils,
                               jinja, debug)
from qutebrowser.mainwindow import messageview, prompt
from qutebrowser.completion import completionwidget, completer
from qutebrowser.keyinput import modeman
from qutebrowser.browser import commands, downloadview, hints, downloads
from qutebrowser.misc import crashsignal, keyhintwidget, sessions


win_id_gen = itertools.count(0)


def get_window(via_ipc, force_window=False, force_tab=False,
               force_target=None, no_raise=False):
    """Helper function for app.py to get a window id.

    Args:
        via_ipc: Whether the request was made via IPC.
        force_window: Whether to force opening in a window.
        force_tab: Whether to force opening in a tab.
        force_target: Override the new_instance_open_target config
        no_raise: suppress target window raising

    Return:
        ID of a window that was used to open URL
    """
    if force_window and force_tab:
        raise ValueError("force_window and force_tab are mutually exclusive!")

    if not via_ipc:
        # Initial main window
        return 0

    open_target = config.val.new_instance_open_target

    # Apply any target overrides, ordered by precedence
    if force_target is not None:
        open_target = force_target
    if force_window:
        open_target = 'window'
    if force_tab and open_target == 'window':
        # Command sent via IPC
        open_target = 'tab-silent'

    window = None
    should_raise = False

    # Try to find the existing tab target if opening in a tab
    if open_target != 'window':
        window = get_target_window()
        should_raise = open_target not in ['tab-silent', 'tab-bg-silent']

    # Otherwise, or if no window was found, create a new one
    if window is None:
        window = MainWindow(private=None)
        window.show()
        should_raise = True

    if should_raise and not no_raise:
        raise_window(window)

    return window.win_id


def raise_window(window, alert=True):
    """Raise the given MainWindow object."""
    window.setWindowState(window.windowState() & ~Qt.WindowMinimized)
    window.setWindowState(window.windowState() | Qt.WindowActive)
    window.raise_()
    # WORKAROUND for https://bugreports.qt.io/browse/QTBUG-69568
    QCoreApplication.processEvents(  # type: ignore[call-overload]
        QEventLoop.ExcludeUserInputEvents | QEventLoop.ExcludeSocketNotifiers)
    window.activateWindow()

    if alert:
        QApplication.instance().alert(window)


def get_target_window():
    """Get the target window for new tabs, or None if none exist."""
    try:
        win_mode = config.val.new_instance_open_target_window
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


_OverlayInfoType = typing.Tuple[QWidget, pyqtSignal, bool, str]


class MainWindow(QWidget):

    """The main window of qutebrowser.

    Adds all needed components to a vbox, initializes sub-widgets and connects
    signals.

    Attributes:
        status: The StatusBar widget.
        tabbed_browser: The TabbedBrowser widget.
        state_before_fullscreen: window state before activation of fullscreen.
        _downloadview: The DownloadView widget.
        _download_model: The DownloadModel instance.
        _vbox: The main QVBoxLayout.
        _commandrunner: The main CommandRunner instance.
        _overlays: Widgets shown as overlay for the current webpage.
        _private: Whether the window is in private browsing mode.
    """

    # Application wide stylesheets
    STYLESHEET = """
        HintLabel {
            background-color: {{ conf.colors.hints.bg }};
            color: {{ conf.colors.hints.fg }};
            font: {{ conf.fonts.hints }};
            border: {{ conf.hints.border }};
            border-radius: {{ conf.hints.radius }}px;
            padding-top: {{ conf.hints.padding['top'] }}px;
            padding-left: {{ conf.hints.padding['left'] }}px;
            padding-right: {{ conf.hints.padding['right'] }}px;
            padding-bottom: {{ conf.hints.padding['bottom'] }}px;
        }

        QMenu {
            {% if conf.fonts.contextmenu %}
                font: {{ conf.fonts.contextmenu }};
            {% endif %}
            {% if conf.colors.contextmenu.menu.bg %}
                background-color: {{ conf.colors.contextmenu.menu.bg }};
            {% endif %}
            {% if conf.colors.contextmenu.menu.fg %}
                color: {{ conf.colors.contextmenu.menu.fg }};
            {% endif %}
        }

        QMenu::item:selected {
            {% if conf.colors.contextmenu.selected.bg %}
                background-color: {{ conf.colors.contextmenu.selected.bg }};
            {% endif %}
            {% if conf.colors.contextmenu.selected.fg %}
                color: {{ conf.colors.contextmenu.selected.fg }};
            {% endif %}
        }

        QMenu::item:disabled {
            {% if conf.colors.contextmenu.disabled.bg %}
                background-color: {{ conf.colors.contextmenu.disabled.bg }};
            {% endif %}
            {% if conf.colors.contextmenu.disabled.fg %}
                color: {{ conf.colors.contextmenu.disabled.fg }};
            {% endif %}
        }
    """

    def __init__(self, *, private, geometry=None, parent=None):
        """Create a new main window.

        Args:
            geometry: The geometry to load, as a bytes-object (or None).
            private: Whether the window is in private browsing mode.
            parent: The parent the window should get.
        """
        super().__init__(parent)
        # Late import to avoid a circular dependency
        # - browsertab -> hints -> webelem -> mainwindow -> bar -> browsertab
        from qutebrowser.mainwindow import tabbedbrowser
        from qutebrowser.mainwindow.statusbar import bar

        self.setAttribute(Qt.WA_DeleteOnClose)
        self._overlays = []  # type: typing.MutableSequence[_OverlayInfoType]
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
        self._downloadview = downloadview.DownloadView(
            model=self._download_model)

        if config.val.content.private_browsing:
            # This setting always trumps what's passed in.
            private = True
        else:
            private = bool(private)
        self._private = private
        self.tabbed_browser = tabbedbrowser.TabbedBrowser(win_id=self.win_id,
                                                          private=private,
                                                          parent=self)
        objreg.register('tabbed-browser', self.tabbed_browser, scope='window',
                        window=self.win_id)
        self._init_command_dispatcher()

        # We need to set an explicit parent for StatusBar because it does some
        # show/hide magic immediately which would mean it'd show up as a
        # window.
        self.status = bar.StatusBar(win_id=self.win_id, private=private,
                                    parent=self)

        self._add_widgets()
        self._downloadview.show()

        self._init_completion()

        log.init.debug("Initializing modes...")
        modeman.init(win_id=self.win_id, parent=self)

        self._commandrunner = runners.CommandRunner(self.win_id,
                                                    partial_match=True)

        self._keyhint = keyhintwidget.KeyHintView(self.win_id, self)
        self._add_overlay(self._keyhint, self._keyhint.update_geometry)

        self._prompt_container = prompt.PromptContainer(self.win_id, self)
        self._add_overlay(self._prompt_container,
                          self._prompt_container.update_geometry,
                          centered=True, padding=10)
        objreg.register('prompt-container', self._prompt_container,
                        scope='window', window=self.win_id, command_only=True)
        self._prompt_container.hide()

        self._messageview = messageview.MessageView(parent=self)
        self._add_overlay(self._messageview, self._messageview.update_geometry)

        self._init_geometry(geometry)
        self._connect_signals()

        # When we're here the statusbar might not even really exist yet, so
        # resizing will fail. Therefore, we use singleShot QTimers to make sure
        # we defer this until everything else is initialized.
        QTimer.singleShot(0, self._connect_overlay_signals)
        config.instance.changed.connect(self._on_config_changed)

        QApplication.instance().new_window.emit(self)
        self._set_decoration(config.val.window.hide_decoration)

        self.state_before_fullscreen = self.windowState()
        stylesheet.set_register(self)

    def _init_geometry(self, geometry):
        """Initialize the window geometry or load it from disk."""
        if geometry is not None:
            self._load_geometry(geometry)
        elif self.win_id == 0:
            self._load_state_geometry()
        else:
            self._set_default_geometry()
        log.init.debug("Initial main window geometry: {}".format(
            self.geometry()))

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
            left = (self.width() - width) // 2 if centered else 0

        height_padding = 20
        status_position = config.val.statusbar.position
        if status_position == 'bottom':
            if self.status.isVisible():
                status_height = self.status.height()
                bottom = self.status.geometry().top()
            else:
                status_height = 0
                bottom = self.height()
            top = self.height() - status_height - size_hint.height()
            top = qtutils.check_overflow(top, 'int', fatal=False)
            topleft = QPoint(left, max(height_padding, top))
            bottomright = QPoint(left + width, bottom)
        elif status_position == 'top':
            if self.status.isVisible():
                status_height = self.status.height()
                top = self.status.geometry().bottom()
            else:
                status_height = 0
                top = 0
            topleft = QPoint(left, top)
            bottom = status_height + size_hint.height()
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
        qtnetwork_download_manager = objreg.get('qtnetwork-download-manager')

        try:
            webengine_download_manager = objreg.get(
                'webengine-download-manager')
        except KeyError:
            webengine_download_manager = None

        self._download_model = downloads.DownloadModel(
            qtnetwork_download_manager, webengine_download_manager)
        objreg.register('download-model', self._download_model,
                        scope='window', window=self.win_id,
                        command_only=True)

    def _init_completion(self):
        self._completion = completionwidget.CompletionView(cmd=self.status.cmd,
                                                           win_id=self.win_id,
                                                           parent=self)
        completer_obj = completer.Completer(cmd=self.status.cmd,
                                            win_id=self.win_id,
                                            parent=self._completion)
        self._completion.selection_changed.connect(
            completer_obj.on_selection_changed)
        objreg.register('completion', self._completion, scope='window',
                        window=self.win_id, command_only=True)
        self._add_overlay(self._completion, self._completion.update_geometry)

    def _init_command_dispatcher(self):
        self._command_dispatcher = commands.CommandDispatcher(
            self.win_id, self.tabbed_browser)
        objreg.register('command-dispatcher',
                        self._command_dispatcher,
                        command_only=True,
                        scope='window', window=self.win_id)

        widget = self.tabbed_browser.widget
        widget.destroyed.connect(
            functools.partial(objreg.delete, 'command-dispatcher',
                              scope='window', window=self.win_id))

    def __repr__(self):
        return utils.get_repr(self)

    @pyqtSlot(str)
    def _on_config_changed(self, option):
        """Resize the completion if related config options changed."""
        if option == 'statusbar.padding':
            self._update_overlay_geometries()
        elif option == 'downloads.position':
            self._add_widgets()
        elif option == 'statusbar.position':
            self._add_widgets()
            self._update_overlay_geometries()
        elif option == 'window.hide_decoration':
            self._set_decoration(config.val.window.hide_decoration)

    def _add_widgets(self):
        """Add or readd all widgets to the VBox."""
        self._vbox.removeWidget(self.tabbed_browser.widget)
        self._vbox.removeWidget(self._downloadview)
        self._vbox.removeWidget(self.status)
        widgets = [self.tabbed_browser.widget]  # type: typing.List[QWidget]

        downloads_position = config.val.downloads.position
        if downloads_position == 'top':
            widgets.insert(0, self._downloadview)
        elif downloads_position == 'bottom':
            widgets.append(self._downloadview)
        else:
            raise ValueError("Invalid position {}!".format(downloads_position))

        status_position = config.val.statusbar.position
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
        try:
            data = configfiles.state['geometry']['mainwindow']
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
        data = self.saveGeometry().data()
        geom = base64.b64encode(data).decode('ASCII')
        configfiles.state['geometry']['mainwindow'] = geom

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
        message_bridge = self._get_object('message-bridge')
        mode_manager = modeman.instance(self.win_id)

        # misc
        self.tabbed_browser.close_window.connect(self.close)
        mode_manager.entered.connect(hints.on_mode_entered)

        # status bar
        mode_manager.entered.connect(self.status.on_mode_entered)
        mode_manager.left.connect(self.status.on_mode_left)
        mode_manager.left.connect(self.status.cmd.on_mode_left)
        mode_manager.left.connect(
            message.global_bridge.mode_left)  # type: ignore[arg-type]

        # commands
        normal_parser = mode_manager.parsers[usertypes.KeyMode.normal]
        normal_parser.keystring_updated.connect(
            self.status.keystring.setText)
        self.status.cmd.got_cmd[str].connect(  # type: ignore[index]
            self._commandrunner.run_safely)
        self.status.cmd.got_cmd[str, int].connect(  # type: ignore[index]
            self._commandrunner.run_safely)
        self.status.cmd.returnPressed.connect(
            self.tabbed_browser.on_cmd_return_pressed)
        self.status.cmd.got_search.connect(
            self._command_dispatcher.search)

        # key hint popup
        for mode, parser in mode_manager.parsers.items():
            parser.keystring_updated.connect(functools.partial(
                self._keyhint.update_keyhint, mode.name))

        # messages
        message.global_bridge.show_message.connect(
            self._messageview.show_message)
        message.global_bridge.flush()
        message.global_bridge.clear_messages.connect(
            self._messageview.clear_messages)

        message_bridge.s_set_text.connect(self.status.set_text)
        message_bridge.s_maybe_reset_text.connect(
            self.status.txt.maybe_reset_text)

        # statusbar
        self.tabbed_browser.current_tab_changed.connect(
            self.status.on_tab_changed)

        self.tabbed_browser.cur_progress.connect(
            self.status.prog.on_load_progress)
        self.tabbed_browser.cur_load_started.connect(
            self.status.prog.on_load_started)

        self.tabbed_browser.cur_scroll_perc_changed.connect(
            self.status.percentage.set_perc)
        self.tabbed_browser.widget.tab_index_changed.connect(
            self.status.tabindex.on_tab_index_changed)

        self.tabbed_browser.cur_url_changed.connect(
            self.status.url.set_url)
        self.tabbed_browser.cur_url_changed.connect(functools.partial(
            self.status.backforward.on_tab_cur_url_changed,
            tabs=self.tabbed_browser))
        self.tabbed_browser.cur_link_hovered.connect(
            self.status.url.set_hover_url)
        self.tabbed_browser.cur_load_status_changed.connect(
            self.status.url.on_load_status_changed)

        self.tabbed_browser.cur_caret_selection_toggled.connect(
            self.status.on_caret_selection_toggled)

        self.tabbed_browser.cur_fullscreen_requested.connect(
            self._on_fullscreen_requested)
        self.tabbed_browser.cur_fullscreen_requested.connect(
            self.status.maybe_hide)

        # downloadview
        self.tabbed_browser.cur_fullscreen_requested.connect(
            self._downloadview.on_fullscreen_requested)

        # command input / completion
        mode_manager.entered.connect(
            self.tabbed_browser.on_mode_entered)
        mode_manager.left.connect(
            self.tabbed_browser.on_mode_left)
        self.status.cmd.clear_completion_selection.connect(
            self._completion.on_clear_completion_selection)
        self.status.cmd.hide_completion.connect(
            self._completion.hide)

    def _set_decoration(self, hidden):
        """Set the visibility of the window decoration via Qt."""
        window_flags = Qt.Window  # type: int
        refresh_window = self.isVisible()
        if hidden:
            window_flags |= Qt.CustomizeWindowHint | Qt.NoDropShadowWindowHint
        self.setWindowFlags(typing.cast(Qt.WindowFlags, window_flags))
        if refresh_window:
            self.show()

    @pyqtSlot(bool)
    def _on_fullscreen_requested(self, on):
        if not config.val.content.fullscreen.window:
            if on:
                self.state_before_fullscreen = self.windowState()
                self.setWindowState(
                    Qt.WindowFullScreen |  # type: ignore[arg-type]
                    self.state_before_fullscreen)  # type: ignore[operator]
            elif self.isFullScreen():
                self.setWindowState(self.state_before_fullscreen)
        log.misc.debug('on: {}, state before fullscreen: {}'.format(
            on, debug.qflags_key(Qt, self.state_before_fullscreen)))

    @cmdutils.register(instance='main-window', scope='window')
    @pyqtSlot()
    def close(self):
        """Close the current window.

        //

        Extend close() so we can register it as a command.
        """
        super().close()

    def resizeEvent(self, e):
        """Extend resizewindow's resizeEvent to adjust completion.

        Args:
            e: The QResizeEvent
        """
        super().resizeEvent(e)
        self._update_overlay_geometries()
        self._downloadview.updateGeometry()
        self.tabbed_browser.widget.tabBar().refresh()

    def showEvent(self, e):
        """Extend showEvent to register us as the last-visible-main-window.

        Args:
            e: The QShowEvent
        """
        super().showEvent(e)
        objreg.register('last-visible-main-window', self, update=True)

    def _confirm_quit(self):
        """Confirm that this window should be closed.

        Return:
            True if closing is okay, False if a closeEvent should be ignored.
        """
        tab_count = self.tabbed_browser.widget.count()
        download_count = self._download_model.running_downloads()
        quit_texts = []
        # Ask if multiple-tabs are open
        if 'multiple-tabs' in config.val.confirm_quit and tab_count > 1:
            quit_texts.append("{} tabs are open.".format(tab_count))
        # Ask if multiple downloads running
        if 'downloads' in config.val.confirm_quit and download_count > 0:
            quit_texts.append("{} {} running.".format(
                download_count,
                "download is" if download_count == 1 else "downloads are"))
        # Process all quit messages that user must confirm
        if quit_texts or 'always' in config.val.confirm_quit:
            msg = jinja.environment.from_string("""
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
                return False

        return True

    def closeEvent(self, e):
        """Override closeEvent to display a confirmation if needed."""
        if crashsignal.crash_handler.is_crashing:
            e.accept()
            return

        if not self._confirm_quit():
            e.ignore()
            return

        e.accept()

        try:
            last_visible = objreg.get('last-visible-main-window')
            if self is last_visible:
                objreg.delete('last-visible-main-window')
        except KeyError:
            pass

        sessions.session_manager.save_last_window_session()
        self._save_geometry()
        log.destroy.debug("Closing window {}".format(self.win_id))
