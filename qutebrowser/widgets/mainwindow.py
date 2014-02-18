# Copyright 2014 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""The main window of QuteBrowser."""

import binascii
from base64 import b64decode

from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from qutebrowser.widgets.statusbar import StatusBar
from qutebrowser.widgets.browser import TabbedBrowser
from qutebrowser.widgets.completion import CompletionView
import qutebrowser.utils.config as config


class MainWindow(QWidget):

    """The main window of QuteBrowser.

    Adds all needed components to a vbox, initializes subwidgets and connects
    signals.

    Attributes:
        tabs: The TabbedBrowser widget.
        status: The StatusBar widget.
        _vbox: The main QVBoxLayout.

    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle('qutebrowser')
        try:
            geom = b64decode(config.state['geometry']['mainwindow'],
                             validate=True)
        except (KeyError, binascii.Error):
            self._set_default_geometry()
        else:
            try:
                ok = self.restoreGeometry(geom)
            except KeyError:
                self._set_default_geometry()
            if not ok:
                self._set_default_geometry()

        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(0)

        self.tabs = TabbedBrowser()
        self._vbox.addWidget(self.tabs)

        self.completion = CompletionView(self)

        self.status = StatusBar()
        self._vbox.addWidget(self.status)

        self.status.resized.connect(self.completion.resize_to_bar)
        self.status.moved.connect(self.completion.move_to_bar)
        self.tabs.cur_progress.connect(self.status.prog.setValue)
        self.tabs.cur_load_finished.connect(lambda *args:
                                            self.status.prog.hide())
        self.tabs.cur_load_finished.connect(
            self.status.url.on_loading_finished)
        self.tabs.cur_load_started.connect(self.status.prog.on_load_started)
        self.tabs.cur_scroll_perc_changed.connect(
            self.status.percentage.set_perc)
        self.tabs.cur_statusbar_message.connect(self.status.txt.setText)
        self.tabs.cur_url_changed.connect(self.status.url.set_url)
        self.tabs.cur_link_hovered.connect(self.status.url.set_hover_url)
        self.status.cmd.esc_pressed.connect(self.tabs.setFocus)
        self.status.cmd.hide_completion.connect(self.completion.hide)
        self.status.cmd.textChanged.connect(
            self.completion.on_cmd_text_changed)
        self.status.cmd.tab_pressed.connect(self.completion.on_tab_pressed)
        self.completion.append_cmd_text.connect(
            self.status.cmd.on_append_cmd_text)

        #self.retranslateUi(MainWindow)
        #self.tabWidget.setCurrentIndex(0)
        #QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def _set_default_geometry(self):
        """Set some sensible default geometry."""
        self.setGeometry(QRect(50, 50, 800, 600))
