# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

from PyQt5.QtCore import pyqtSlot, QRect, QPoint, QTimer, Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication

from qutebrowser.commands import runners, cmdutils
from qutebrowser.config import config
from qutebrowser.utils import message, log, usertypes, qtutils, objreg, utils
from qutebrowser.mainwindow import tabbedbrowser
from qutebrowser.mainwindow.statusbar import bar
from qutebrowser.completion import completionwidget
from qutebrowser.keyinput import modeman
from qutebrowser.browser import hints, downloads, downloadview, commands
from qutebrowser.misc import crashsignal


win_id_gen = itertools.count(0)


def get_window(via_ipc, force_window=False, force_tab=False):
    """Helper function for app.py to get a window id.

    Args:
        via_ipc: Whether the request was made via IPC.
        force_window: Whether to force opening in a window.
        force_tab: Whether to force opening in a tab.
    """
    if force_window and force_tab:
        raise ValueError("force_window and force_tab are mutually exclusive!")
    if not via_ipc:
        # Initial main window
        return 0
    window_to_raise = None
    open_target = config.get('general', 'new-instance-open-target')
    if (open_target == 'window' or force_window) and not force_tab:
        window = MainWindow()
        window.show()
        win_id = window.win_id
        window_to_raise = window
    else:
        try:
            window = objreg.last_window()
        except objreg.NoWindow:
            # There is no window left, so we open a new one
            window = MainWindow()
            window.show()
            win_id = window.win_id
            window_to_raise = window
        win_id = window.win_id
        if open_target not in ('tab-silent', 'tab-bg-silent'):
            window_to_raise = window
    if window_to_raise is not None:
        window_to_raise.setWindowState(window.windowState() &
                                       ~Qt.WindowMinimized | Qt.WindowActive)
        window_to_raise.raise_()
        window_to_raise.activateWindow()
        QApplication.instance().alert(window_to_raise)
    return win_id


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

        log.init.debug("Initializing downloads...")
        download_manager = downloads.DownloadManager(self.win_id, self)
        objreg.register('download-manager', download_manager, scope='window',
                        window=self.win_id)

        self._downloadview = downloadview.DownloadView(self.win_id)

        self.tabbed_browser = tabbedbrowser.TabbedBrowser(self.win_id)
        objreg.register('tabbed-browser', self.tabbed_browser, scope='window',
                        window=self.win_id)
        dispatcher = commands.CommandDispatcher(self.win_id,
                                                self.tabbed_browser)
        objreg.register('command-dispatcher', dispatcher, scope='window',
                        window=self.win_id)
        self.tabbed_browser.destroyed.connect(
            functools.partial(objreg.delete, 'command-dispatcher',
                              scope='window', window=self.win_id))

        # We need to set an explicit parent for StatusBar because it does some
        # show/hide magic immediately which would mean it'd show up as a
        # window.
        self.status = bar.StatusBar(self.win_id, parent=self)

        self._add_widgets()
        self._downloadview.show()

        self._completion = completionwidget.CompletionView(self.win_id, self)

        self._commandrunner = runners.CommandRunner(self.win_id)

        log.init.debug("Initializing modes...")
        modeman.init(self.win_id, self)

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
        QTimer.singleShot(0, self._connect_resize_completion)
        objreg.get('config').changed.connect(self.on_config_changed)

        if config.get('ui', 'hide-mouse-cursor'):
            self.setCursor(Qt.BlankCursor)

        #self.retranslateUi(MainWindow)
        #self.tabWidget.setCurrentIndex(0)
        #QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def __repr__(self):
        return utils.get_repr(self)

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Resize the completion if related config options changed."""
        if section == 'completion' and option in ('height', 'shrink'):
            self.resize_completion()
        elif section == 'ui' and option == 'statusbar-padding':
            self.resize_completion()
        elif section == 'ui' and option == 'downloads-position':
            self._add_widgets()

    def _add_widgets(self):
        """Add or readd all widgets to the VBox."""
        self._vbox.removeWidget(self.tabbed_browser)
        self._vbox.removeWidget(self._downloadview)
        self._vbox.removeWidget(self.status)
        position = config.get('ui', 'downloads-position')
        if position == 'top':
            self._vbox.addWidget(self._downloadview)
            self._vbox.addWidget(self.tabbed_browser)
        elif position == 'bottom':
            self._vbox.addWidget(self.tabbed_browser)
            self._vbox.addWidget(self._downloadview)
        else:
            raise ValueError("Invalid position {}!".format(position))
        self._vbox.addWidget(self.status)

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
        log.init.debug("Loading mainwindow from {}".format(geom))
        ok = self.restoreGeometry(geom)
        if not ok:
            log.init.warning("Error while loading geometry.")
            self._set_default_geometry()

    def _connect_resize_completion(self):
        """Connect the resize_completion signal and resize it once."""
        self._completion.resize_completion.connect(self.resize_completion)
        self.resize_completion()

    def _set_default_geometry(self):
        """Set some sensible default geometry."""
        self.setGeometry(QRect(50, 50, 800, 600))

    def _get_object(self, name):
        """Get an object for this window in the object registry."""
        return objreg.get(name, scope='window', window=self.win_id)

    def _connect_signals(self):
        """Connect all mainwindow signals."""
        # pylint: disable=too-many-statements
        key_config = objreg.get('key-config')

        status = self._get_object('statusbar')
        keyparsers = self._get_object('keyparsers')
        completion_obj = self._get_object('completion')
        tabs = self._get_object('tabbed-browser')
        cmd = self._get_object('status-command')
        message_bridge = self._get_object('message-bridge')
        mode_manager = self._get_object('mode-manager')
        prompter = self._get_object('prompter')

        # misc
        self.tabbed_browser.close_window.connect(self.close)
        mode_manager.entered.connect(hints.on_mode_entered)

        # status bar
        mode_manager.entered.connect(status.on_mode_entered)
        mode_manager.left.connect(status.on_mode_left)
        mode_manager.left.connect(cmd.on_mode_left)
        mode_manager.left.connect(prompter.on_mode_left)

        # commands
        keyparsers[usertypes.KeyMode.normal].keystring_updated.connect(
            status.keystring.setText)
        cmd.got_cmd.connect(self._commandrunner.run_safely)
        cmd.returnPressed.connect(tabs.on_cmd_return_pressed)
        tabs.got_cmd.connect(self._commandrunner.run_safely)

        # config
        for obj in keyparsers.values():
            key_config.changed.connect(obj.on_keyconfig_changed)

        # messages
        message_bridge.s_error.connect(status.disp_error)
        message_bridge.s_warning.connect(status.disp_warning)
        message_bridge.s_info.connect(status.disp_temp_text)
        message_bridge.s_set_text.connect(status.set_text)
        message_bridge.s_maybe_reset_text.connect(status.txt.maybe_reset_text)
        message_bridge.s_set_cmd_text.connect(cmd.set_cmd_text)
        message_bridge.s_question.connect(prompter.ask_question,
                                          Qt.DirectConnection)

        # statusbar
        # FIXME some of these probably only should be triggered on mainframe
        # loadStarted.
        # https://github.com/The-Compiler/qutebrowser/issues/112
        tabs.current_tab_changed.connect(status.prog.on_tab_changed)
        tabs.cur_progress.connect(status.prog.setValue)
        tabs.cur_load_finished.connect(status.prog.hide)
        tabs.cur_load_started.connect(status.prog.on_load_started)

        tabs.current_tab_changed.connect(status.percentage.on_tab_changed)
        tabs.cur_scroll_perc_changed.connect(status.percentage.set_perc)

        tabs.tab_index_changed.connect(status.tabindex.on_tab_index_changed)

        tabs.current_tab_changed.connect(status.txt.on_tab_changed)
        tabs.cur_statusbar_message.connect(status.txt.on_statusbar_message)
        tabs.cur_load_started.connect(status.txt.on_load_started)

        tabs.current_tab_changed.connect(status.url.on_tab_changed)
        tabs.cur_url_text_changed.connect(status.url.set_url)
        tabs.cur_link_hovered.connect(status.url.set_hover_url)
        tabs.cur_load_status_changed.connect(status.url.on_load_status_changed)

        # command input / completion
        mode_manager.left.connect(tabs.on_mode_left)
        cmd.clear_completion_selection.connect(
            completion_obj.on_clear_completion_selection)
        cmd.hide_completion.connect(completion_obj.hide)

    @pyqtSlot()
    def resize_completion(self):
        """Adjust completion according to config."""
        if not self._completion.isVisible():
            # It doesn't make sense to resize the completion as long as it's
            # not shown anyways.
            return
        # Get the configured height/percentage.
        confheight = str(config.get('completion', 'height'))
        if confheight.endswith('%'):
            perc = int(confheight.rstrip('%'))
            height = self.height() * perc / 100
        else:
            height = int(confheight)
        # Shrink to content size if needed and shrinking is enabled
        if config.get('completion', 'shrink'):
            contents_height = (
                self._completion.viewportSizeHint().height() +
                self._completion.horizontalScrollBar().sizeHint().height())
            if contents_height <= height:
                height = contents_height
        else:
            contents_height = -1
        # hpoint now would be the bottom-left edge of the widget if it was on
        # the top of the main window.
        topleft_y = self.height() - self.status.height() - height
        topleft_y = qtutils.check_overflow(topleft_y, 'int', fatal=False)
        topleft = QPoint(0, topleft_y)
        bottomright = self.status.geometry().topRight()
        rect = QRect(topleft, bottomright)
        log.misc.debug('completion rect: {}'.format(rect))
        if rect.isValid():
            self._completion.setGeometry(rect)

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
        self.resize_completion()
        self._downloadview.updateGeometry()
        self.tabbed_browser.tabBar().refresh()

    def _do_close(self):
        """Helper function for closeEvent."""
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
        download_manager = objreg.get('download-manager', scope='window',
                                      window=self.win_id)
        download_count = download_manager.rowCount()
        quit_texts = []
        # Close if set to never ask for confirmation
        if 'never' in confirm_quit:
            pass
        # Ask if multiple-tabs are open
        if 'multiple-tabs' in confirm_quit and tab_count > 1:
            quit_texts.append("{} {} open.".format(
                tab_count, "tab is" if tab_count == 1 else "tabs are"))
        # Ask if multiple downloads running
        if 'downloads' in confirm_quit and download_count > 0:
            quit_texts.append("{} {} running.".format(
                tab_count,
                "download is" if tab_count == 1 else "downloads are"))
        # Process all quit messages that user must confirm
        if quit_texts or 'always' in confirm_quit:
            text = '\n'.join(['Really quit?'] + quit_texts)
            confirmed = message.ask(self.win_id, text,
                                    usertypes.PromptMode.yesno,
                                    default=True)
            # Stop asking if the user cancels
            if not confirmed:
                log.destroy.debug("Cancelling closing of window {}".format(
                    self.win_id))
                e.ignore()
                return
        e.accept()
        self._do_close()
