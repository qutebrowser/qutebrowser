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

from PyQt5.QtCore import Qt, QVariant, QAbstractListModel
from PyQt5.QtWidgets import QApplication


class DownloadModel(QAbstractListModel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.downloadmanager = QApplication.instance().downloadmanager

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
        return str(item.percentage)  # FIXME

    def rowCount(self, parent):
        if parent.isValid():
            # We don't have children
            return 0
        return len(self.downloadmanager.downloads)
