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


class DownloadModel(QAbstractListModel):

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

    @pyqtSlot(int)
    def on_data_changed(self, idx):
        model_idx = self.index(idx, 0)
        self.dataChanged.emit(model_idx, model_idx)

    def headerData(self, section, orientation, role):
        if (section == 0 and orientation == Qt.Horizontal and
                role == Qt.DisplayRole):
            return "Downloads"
        else:
            return ""

    def data(self, index, role):
        if not index.isValid():
            return QVariant()
        elif role != Qt.DisplayRole:
            return QVariant()
        elif index.parent().isValid() or index.column() != 0:
            return QVariant()
        try:
            item = self.downloadmanager.downloads[index.row()]
        except IndexError:
            return QVariant()
        perc = item.percentage
        if perc is None:
            return QVariant()
        else:
            return str(round(perc))  # FIXME

    def rowCount(self, parent):
        if parent.isValid():
            # We don't have children
            return 0
        return len(self.downloadmanager.downloads)
