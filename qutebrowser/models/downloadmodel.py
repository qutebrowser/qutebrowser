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

"""Glue code for qutebrowser.{browser,widgets}.download."""

from PyQt5.QtCore import (pyqtSlot, Qt, QVariant, QAbstractListModel,
                          QModelIndex)
from PyQt5.QtWidgets import QApplication

from qutebrowser.config import config
from qutebrowser.utils import usertypes, qtutils


Role = usertypes.enum('Role', 'item', start=Qt.UserRole, is_int=True)


class DownloadModel(QAbstractListModel):

    """Glue model to show downloads in a QListView.

    Glue between qutebrowser.browser.download (DownloadManager) and
    qutebrowser.widgets.download (DownloadView).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.downloadmanager = QApplication.instance().downloadmanager
        self.downloadmanager.download_about_to_be_added.connect(
            lambda idx: self.beginInsertRows(QModelIndex(), idx, idx))
        self.downloadmanager.download_added.connect(self.endInsertRows)
        self.downloadmanager.download_about_to_be_finished.connect(
            lambda idx: self.beginRemoveRows(QModelIndex(), idx, idx))
        self.downloadmanager.download_finished.connect(self.endRemoveRows)
        self.downloadmanager.data_changed.connect(self.on_data_changed)

    def __repr__(self):
        return '<{}>'.format(self.__class__.__name__)

    @pyqtSlot(int)
    def on_data_changed(self, idx):
        """Update view when DownloadManager data changed."""
        model_idx = self.index(idx, 0)
        qtutils.ensure_valid(model_idx)
        self.dataChanged.emit(model_idx, model_idx)

    def last_index(self):
        """Get the last index in the model.

        Return:
            A (possibly invalid) QModelIndex.
        """
        idx = self.index(self.rowCount() - 1)
        return idx

    def headerData(self, section, orientation, role):
        """Simple constant header."""
        if (section == 0 and orientation == Qt.Horizontal and
                role == Qt.DisplayRole):
            return "Downloads"
        else:
            return ""

    def data(self, index, role):
        """Download data from DownloadManager."""
        qtutils.ensure_valid(index)
        if index.parent().isValid() or index.column() != 0:
            return QVariant()

        item = self.downloadmanager.downloads[index.row()]
        if role == Qt.DisplayRole:
            data = str(item)
        elif role == Qt.ForegroundRole:
            data = config.get('colors', 'downloads.fg')
        elif role == Qt.BackgroundRole:
            data = item.bg_color()
        elif role == Role.item:
            data = item
        else:
            data = QVariant()
        return data

    def flags(self, _index):
        """Override flags so items aren't selectable.

        The default would be Qt.ItemIsEnabled | Qt.ItemIsSelectable."""
        return Qt.ItemIsEnabled

    def rowCount(self, parent=QModelIndex()):
        """Get count of active downloads."""
        if parent.isValid():
            # We don't have children
            return 0
        return len(self.downloadmanager.downloads)
