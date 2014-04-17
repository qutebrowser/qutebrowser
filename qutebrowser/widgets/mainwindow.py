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

from PyQt5.QtCore import pyqtSlot, QRect, QPoint
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebKitWidgets import QWebInspector

from qutebrowser.widgets.statusbar import StatusBar
from qutebrowser.widgets.tabbedbrowser import TabbedBrowser
from qutebrowser.widgets.completion import CompletionView
import qutebrowser.commands.utils as cmdutils
import qutebrowser.config.config as config


class MainWindow(QWidget):

    """The main window of QuteBrowser.

    Adds all needed components to a vbox, initializes subwidgets and connects
    signals.

    Attributes:
        tabs: The TabbedBrowser widget.
        status: The StatusBar widget.
        inspector: The QWebInspector.
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
        self.inspector = QWebInspector()
        self.inspector.hide()
        self._vbox.addWidget(self.inspector)

        self.status = StatusBar()
        self._vbox.addWidget(self.status)

        #self.status.resized.connect(self.completion.resize_to_bar)
        #self.status.moved.connect(self.completion.move_to_bar)
        #self.tabs.resized.connect(self.completion.on_browser_resized)
        self.tabs.cur_progress.connect(self.status.prog.setValue)
        self.tabs.cur_load_finished.connect(self.status.prog.hide)
        self.tabs.cur_load_finished.connect(
            self.status.url.on_loading_finished)
        self.tabs.cur_load_started.connect(self.status.prog.on_load_started)
        self.tabs.cur_scroll_perc_changed.connect(
            self.status.percentage.set_perc)
        self.tabs.cur_statusbar_message.connect(self.status.txt.set_normaltext)
        self.tabs.cur_temp_message.connect(self.status.txt.set_temptext)
        self.tabs.cur_url_changed.connect(self.status.url.set_url)
        self.tabs.cur_link_hovered.connect(self.status.url.set_hover_url)
        self.tabs.currentChanged.connect(self.update_inspector)
        self.status.cmd.esc_pressed.connect(self.tabs.setFocus)
        self.status.cmd.clear_completion_selection.connect(
            self.completion.on_clear_completion_selection)
        self.status.cmd.hide_completion.connect(self.completion.hide)
        self.status.cmd.textChanged.connect(
            self.completion.on_cmd_text_changed)
        self.status.cmd.tab_pressed.connect(self.completion.on_tab_pressed)
        self.completion.change_completed_part.connect(
            self.status.cmd.on_change_completed_part)

        #self.retranslateUi(MainWindow)
        #self.tabWidget.setCurrentIndex(0)
        #QtCore.QMetaObject.connectSlotsByName(MainWindow)

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Resize completion if config changed."""
        if section == 'general' and option == 'completion_height':
            self.resize_completion()

    def resize_completion(self):
        """Adjust completion according to config."""
        confheight = str(config.get('general', 'completion_height'))
        if confheight.endswith('%'):
            perc = int(confheight.rstrip('%'))
            height = self.height() * perc / 100
        else:
            height = int(confheight)
        # hpoint now would be the bottom-left edge of the widget if it was on
        # the top of the main window.
        topleft = QPoint(0, self.height() - self.status.height() - height)
        bottomright = self.status.geometry().topRight()
        self.completion.setGeometry(QRect(topleft, bottomright))

    def _set_default_geometry(self):
        """Set some sensible default geometry."""
        self.setGeometry(QRect(50, 50, 800, 600))

    @cmdutils.register(instance='mainwindow', name='inspector')
    def toggle_inspector(self):
        """Toggle the web inspector."""
        if self.inspector.isVisible():
            self.inspector.hide()
        else:
            if not config.get('webkit', 'developer_extras_enabled'):
                self.status.disp_error("Please enable developer-extras before "
                    "using the webinspector!")
            else:
                self.inspector.show()

    @pyqtSlot()
    def update_inspector(self):
        """Update the web inspector if the page changed."""
        self.inspector.setPage(self.tabs.currentWidget().page())
        if self.inspector.isVisible():
            # For some odd reason, we need to do this so the inspector actually
            # shows some content...
            self.inspector.hide()
            self.inspector.show()

    def resizeEvent(self, e):
        """Extend resizewindow's resizeEvent to adjust completion.

        Args:
            e: The QResizeEvent
        """
        super().resizeEvent(e)
        self.resize_completion()
