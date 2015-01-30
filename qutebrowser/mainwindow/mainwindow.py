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

from PyQt5.QtCore import pyqtSlot, QRect, QPoint, QTimer, Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from qutebrowser.commands import runners, cmdutils
from qutebrowser.config import config
from qutebrowser.utils import message, log, usertypes, qtutils, objreg, utils
from qutebrowser.mainwindow import tabbedbrowser
from qutebrowser.mainwindow.statusbar import bar
from qutebrowser.completion import completionwidget
from qutebrowser.keyinput import modeman
from qutebrowser.browser import hints, downloads, downloadview


win_id_gen = itertools.count(0)


class MainWindow(QWidget):

    """The main window of qutebrowser.

    Adds all needed components to a vbox, initializes subwidgets and connects
    signals.

    Attributes:
        status: The StatusBar widget.
        _downloadview: The DownloadView widget.
        _tabbed_browser: The TabbedBrowser widget.
        _vbox: The main QVBoxLayout.
        _commandrunner: The main CommandRunner instance.
    """

    def __init__(self, win_id, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._commandrunner = None
        self.win_id = win_id
        self.registry = objreg.ObjectRegistry()
        objreg.window_registry[win_id] = self
        objreg.register('main-window', self, scope='window', window=win_id)
        tab_registry = objreg.ObjectRegistry()
        objreg.register('tab-registry', tab_registry, scope='window',
                        window=win_id)

        message_bridge = message.MessageBridge(self)
        objreg.register('message-bridge', message_bridge, scope='window',
                        window=win_id)

        self.setWindowTitle('qutebrowser')
        if win_id == 0:
            self._load_geometry()
        else:
            self._set_default_geometry()
        log.init.debug("Initial mainwindow geometry: {}".format(
            self.geometry()))
        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(0)

        log.init.debug("Initializing downloads...")
        download_manager = downloads.DownloadManager(win_id, self)
        objreg.register('download-manager', download_manager, scope='window',
                        window=win_id)

        self._downloadview = downloadview.DownloadView(win_id)
        self._vbox.addWidget(self._downloadview)
        self._downloadview.show()

        self._tabbed_browser = tabbedbrowser.TabbedBrowser(win_id)
        objreg.register('tabbed-browser', self._tabbed_browser, scope='window',
                        window=win_id)
        self._vbox.addWidget(self._tabbed_browser)

        # We need to set an explicit parent for StatusBar because it does some
        # show/hide magic immediately which would mean it'd show up as a
        # window.
        self.status = bar.StatusBar(win_id, parent=self)
        self._vbox.addWidget(self.status)

        self._completion = completionwidget.CompletionView(win_id, self)

        self._commandrunner = runners.CommandRunner(win_id)

        log.init.debug("Initializing search...")
        search_runner = runners.SearchRunner(self)
        objreg.register('search-runner', search_runner, scope='window',
                        window=win_id)

        log.init.debug("Initializing modes...")
        modeman.init(self.win_id, self)

        self._connect_signals()

        # When we're here the statusbar might not even really exist yet, so
        # resizing will fail. Therefore, we use singleShot QTimers to make sure
        # we defer this until everything else is initialized.
        QTimer.singleShot(0, self._connect_resize_completion)
        objreg.get('config').changed.connect(self.on_config_changed)
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

    @classmethod
    def spawn(cls, show=True):
        """Create a new main window.

        Args:
            show: Show the window after creating.

        Return:
            The new window id.
        """
        win_id = next(win_id_gen)
        win = MainWindow(win_id)
        if show:
            win.show()
        return win_id

    def _load_geometry(self):
        """Load the geometry from the state file."""
        state_config = objreg.get('state-config')
        try:
            data = state_config['geometry']['mainwindow']
            log.init.debug("Restoring mainwindow from {}".format(data))
            geom = base64.b64decode(data, validate=True)
        except KeyError:
            # First start
            self._set_default_geometry()
        except binascii.Error:
            log.init.exception("Error while reading geometry")
            self._set_default_geometry()
        else:
            try:
                ok = self.restoreGeometry(geom)
            except KeyError:
                log.init.exception("Error while restoring geometry.")
                self._set_default_geometry()
            if not ok:
                log.init.warning("Error while restoring geometry.")
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
        # pylint: disable=too-many-locals,too-many-statements
        key_config = objreg.get('key-config')

        status = self._get_object('statusbar')
        keyparsers = self._get_object('keyparsers')
        completion_obj = self._get_object('completion')
        tabs = self._get_object('tabbed-browser')
        cmd = self._get_object('status-command')
        completer = self._get_object('completer')
        search_runner = self._get_object('search-runner')
        message_bridge = self._get_object('message-bridge')
        mode_manager = self._get_object('mode-manager')
        prompter = self._get_object('prompter')

        # misc
        self._tabbed_browser.close_window.connect(self.close)
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
        cmd.got_search.connect(search_runner.search)
        cmd.got_search_rev.connect(search_runner.search_rev)
        cmd.returnPressed.connect(tabs.on_cmd_return_pressed)
        search_runner.do_search.connect(tabs.search)
        tabs.got_cmd.connect(self._commandrunner.run_safely)

        # config
        for obj in keyparsers.values():
            key_config.changed.connect(obj.on_keyconfig_changed)

        # messages
        message_bridge.s_error.connect(status.disp_error)
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

        # quickmark completion
        quickmark_manager = objreg.get('quickmark-manager')
        quickmark_manager.changed.connect(completer.init_quickmark_completions)

    @pyqtSlot()
    def resize_completion(self):
        """Adjust completion according to config."""
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

    def resizeEvent(self, e):
        """Extend resizewindow's resizeEvent to adjust completion.

        Args:
            e: The QResizeEvent
        """
        super().resizeEvent(e)
        self.resize_completion()
        self._downloadview.updateGeometry()
        self._tabbed_browser.tabBar().refresh()

    def closeEvent(self, e):
        """Override closeEvent to display a confirmation if needed."""
        confirm_quit = config.get('ui', 'confirm-quit')
        count = self._tabbed_browser.count()
        if confirm_quit == 'never':
            pass
        elif confirm_quit == 'multiple-tabs' and count <= 1:
            pass
        else:
            text = "Close {} {}?".format(
                count, "tab" if count == 1 else "tabs")
            confirmed = message.ask(self.win_id, text,
                                    usertypes.PromptMode.yesno, default=True)
            if not confirmed:
                log.destroy.debug("Cancelling losing of window {}".format(
                    self.win_id))
                e.ignore()
                return
        e.accept()
        objreg.get('app').geometry = bytes(self.saveGeometry())
        log.destroy.debug("Closing window {}".format(self.win_id))
        self._tabbed_browser.shutdown()
