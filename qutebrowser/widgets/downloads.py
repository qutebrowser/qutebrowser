# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

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

from qutebrowser.browser import downloads
from qutebrowser.config import style
from qutebrowser.utils import qtutils, utils, objreg


class DownloadView(QListView):

    """QListView which shows currently running downloads as a bar.

    Attributes:
        _menu: The QMenu which is currently displayed.
        _model: The currently set model.
    """

    STYLESHEET = """
        QListView {
            {{ color['downloads.bg.bar'] }}
            {{ font['downloads'] }}
        }

        QListView::item {
            padding-right: 2px;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        style.set_register_stylesheet(self)
        self.setResizeMode(QListView.Adjust)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.setFlow(QListView.LeftToRight)
        self._menu = None
        model = objreg.get('download-manager')
        model.rowsInserted.connect(self.updateGeometry)
        model.rowsRemoved.connect(self.updateGeometry)
        self.setModel(model)
        self.setWrapping(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def __repr__(self):
        model = self.model()
        if model is None:
            count = 'None'
        else:
            count = model.rowCount()
        return utils.get_repr(self, count=count)

    @pyqtSlot('QPoint')
    def show_context_menu(self, point):
        """Show the context menu."""
        index = self.indexAt(point)
        if not index.isValid():
            return
        item = self.model().data(index, downloads.ModelRole.item)
        self._menu = QMenu(self)
        cancel = self._menu.addAction("Cancel")
        cancel.triggered.connect(item.cancel)
        self._menu.popup(self.viewport().mapToGlobal(point))

    def minimumSizeHint(self):
        """Override minimumSizeHint so the size is correct in a layout."""
        return self.sizeHint()

    def sizeHint(self):
        """Return sizeHint based on the view contents."""
        try:
            idx = self.model().last_index()
        except RuntimeError:
            pass
        height = self.visualRect(idx).bottom()
        if height != -1:
            size = QSize(0, height + 2)
        else:
            size = QSize(0, 0)
        qtutils.ensure_valid(size)
        return size
