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

"""The main window of qutebrowser."""

import binascii
from base64 import b64decode

from PyQt5.QtCore import pyqtSlot, QRect, QPoint, QCoreApplication
from PyQt5.QtWidgets import QWidget, QVBoxLayout

import qutebrowser.commands.utils as cmdutils
import qutebrowser.config.config as config
import qutebrowser.utils.misc as utils
import qutebrowser.utils.message as message
from qutebrowser.widgets.statusbar.bar import StatusBar
from qutebrowser.widgets.tabbedbrowser import TabbedBrowser
from qutebrowser.widgets.completion import CompletionView
from qutebrowser.widgets.downloads import DownloadView
from qutebrowser.utils.usertypes import PromptMode


class MainWindow(QWidget):

    """The main window of qutebrowser.

    Adds all needed components to a vbox, initializes subwidgets and connects
    signals.

    Attributes:
        tabs: The TabbedBrowser widget.
        status: The StatusBar widget.
        downloadview: The DownloadView widget.
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

        self.downloadview = DownloadView()
        self._vbox.addWidget(self.downloadview)
        self.downloadview.show()

        self.tabs = TabbedBrowser()
        self._vbox.addWidget(self.tabs)

        self.completion = CompletionView(self)
        self.completion.resize_completion.connect(self.resize_completion)

        self.status = StatusBar()
        self._vbox.addWidget(self.status)

        self.resize_completion()
        #self.retranslateUi(MainWindow)
        #self.tabWidget.setCurrentIndex(0)
        #QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def __repr__(self):
        return '<MainWindow>'

    def _set_default_geometry(self):
        """Set some sensible default geometry."""
        self.setGeometry(QRect(50, 50, 800, 600))

    @pyqtSlot(str, str)
    def on_config_changed(self, section, option):
        """Resize completion if config changed."""
        if section == 'completion' and option in ('height', 'shrink'):
            self.resize_completion()

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
                self.completion.viewportSizeHint().height() +
                self.completion.horizontalScrollBar().sizeHint().height())
            if contents_height <= height:
                height = contents_height
        # hpoint now would be the bottom-left edge of the widget if it was on
        # the top of the main window.
        topleft_y = self.height() - self.status.height() - height
        topleft_y = utils.check_overflow(topleft_y, 'int', fatal=False)
        topleft = QPoint(0, topleft_y)
        bottomright = self.status.geometry().topRight()
        self.completion.setGeometry(QRect(topleft, bottomright))

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
        self.downloadview.updateGeometry()

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
