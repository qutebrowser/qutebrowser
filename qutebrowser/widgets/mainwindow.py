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

from PyQt5.QtCore import pyqtSlot, QRect, QPoint, QCoreApplication, Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSplitter
from PyQt5.QtWebKitWidgets import QWebInspector

import qutebrowser.commands.utils as cmdutils
import qutebrowser.config.config as config
import qutebrowser.utils.misc as utils
import qutebrowser.utils.message as message
from qutebrowser.widgets.statusbar.bar import StatusBar
from qutebrowser.widgets._tabbedbrowser import TabbedBrowser
from qutebrowser.widgets._completion import CompletionView
from qutebrowser.utils.usertypes import PromptMode


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
            stateconf = QCoreApplication.instance().stateconfig
            geom = b64decode(stateconf['geometry']['mainwindow'],
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

        self._splitter = QSplitter(self, orientation=Qt.Vertical)

        self.tabs = TabbedBrowser()
        self._splitter.addWidget(self.tabs)

        self.completion = CompletionView(self)
        self.inspector = QWebInspector()
        self.inspector.hide()
        self._splitter.addWidget(self.inspector)
        self._splitter.setStretchFactor(0, 50)

        self._vbox.addWidget(self._splitter)

        self.status = StatusBar()
        self._vbox.addWidget(self.status)

        #self.retranslateUi(MainWindow)
        #self.tabWidget.setCurrentIndex(0)
        #QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def _set_default_geometry(self):
        """Set some sensible default geometry."""
        self.setGeometry(QRect(50, 50, 800, 600))

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Resize completion if config changed."""
        if section == 'completion' and option == 'height':
            self.resize_completion()

    def resize_completion(self):
        """Adjust completion according to config."""
        confheight = str(config.get('completion', 'height'))
        if confheight.endswith('%'):
            perc = int(confheight.rstrip('%'))
            height = self.height() * perc / 100
        else:
            height = int(confheight)
        # hpoint now would be the bottom-left edge of the widget if it was on
        # the top of the main window.
        topleft_y = self.height() - self.status.height() - height
        topleft_y = utils.check_overflow(topleft_y, 'int', fatal=False)
        topleft = QPoint(0, topleft_y)
        bottomright = self.status.geometry().topRight()
        self.completion.setGeometry(QRect(topleft, bottomright))

    @cmdutils.register(instance='mainwindow', name='inspector')
    def toggle_inspector(self):
        """Toggle the web inspector."""
        if self.inspector.isVisible():
            self.inspector.hide()
            self.resize_completion()
        else:
            if not config.get('webkit', 'developer-extras-enabled'):
                self.status.disp_error("Please enable developer-extras before "
                                       "using the webinspector!")
            else:
                self.inspector.show()
                self.resize_completion()

    @pyqtSlot()
    def update_inspector(self):
        """Update the web inspector if the page changed."""
        self.inspector.setPage(self.tabs.currentWidget().page())
        if self.inspector.isVisible():
            # For some odd reason, we need to do this so the inspector actually
            # shows some content...
            self.inspector.hide()
            self.inspector.show()

    @cmdutils.register(instance='mainwindow', name=['quit', 'q'], nargs=0)
    def close(self):
        """Extend close() so we can register it as a command."""
        super().close()

    def resizeEvent(self, e):
        """Extend resizewindow's resizeEvent to adjust completion.

        Args:
            e: The QResizeEvent
        """
        super().resizeEvent(e)
        self.resize_completion()

    def closeEvent(self, e):
        """Override closeEvent to display a confirmation if needed."""
        confirm_quit = config.get('ui', 'confirm-quit')
        count = self.tabs.count()
        if confirm_quit == 'never':
            e.accept()
        elif confirm_quit == 'multiple-tabs' and count <= 1:
            e.accept()
        else:
            text = "Close {} {}?".format(
                count, "tab" if count == 1 else "tabs")
            confirmed = message.modular_question(text, PromptMode.yesno,
                                                 default=True)
            if confirmed:
                e.accept()
            else:
                e.ignore()
