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

"""The ListView to display downloads in."""

from PyQt5.QtCore import pyqtSlot, QSize, Qt
from PyQt5.QtWidgets import QListView, QSizePolicy, QMenu

from qutebrowser.models.downloadmodel import DownloadModel, Role
from qutebrowser.config.style import set_register_stylesheet


class DownloadView(QListView):

    """QListView which shows currently running downloads as a bar.

    Attributes:
        _menu: The QMenu which is currently displayed.
        _model: The currently set model.
    """

    STYLESHEET = """
        QListView {{
            {color[downloads.bg.bar]}
            {font[downloads]}
        }}
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        set_register_stylesheet(self)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.setFlow(QListView.LeftToRight)
        self._menu = None
        self._model = DownloadModel()
        self._model.rowsInserted.connect(self.updateGeometry)
        self._model.rowsRemoved.connect(self.updateGeometry)
        self.setModel(self._model)
        self.setWrapping(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    @pyqtSlot('QPoint')
    def show_context_menu(self, point):
        """Show the context menu."""
        index = self.indexAt(point)
        if not index.isValid():
            return
        item = self.model().data(index, Role.item)
        self._menu = QMenu()
        cancel = self._menu.addAction("Cancel")
        cancel.triggered.connect(item.cancel)
        self._menu.popup(self.viewport().mapToGlobal(point))

    def minimumSizeHint(self):
        """Override minimumSizeHint so the size is correct in a layout."""
        return self.sizeHint()

    def sizeHint(self):
        """Return sizeHint based on the view contents."""
        height = self.sizeHintForRow(0)
        if height != -1:
            return QSize(0, height + 2)
        else:
            return QSize(0, 0)
